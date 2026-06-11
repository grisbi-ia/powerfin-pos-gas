"""Cash management — movements, summary, transfers, users online."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import CashMovement, Dispatch, Shift, Transfer
from app.models.user import User
from app.schemas import (
    CashMovementResponse,
    CashSummaryResponse,
    CreateCashMovementRequest,
    CreateTransferRequest,
    OnlineUserResponse,
    TransferResponse,
)

router = APIRouter(prefix="/api/pos", tags=["cash"])


async def _available_cash(db: AsyncSession, shift_id: int) -> Decimal:
    """Calculate available cash for a shift: opening + income + sales - expenses - transfers - safe_drops."""
    shift = (await db.execute(
        select(Shift).where(Shift.shift_id == shift_id)
    )).scalar_one_or_none()
    if not shift:
        return Decimal("0")

    income = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type.in_(["INCOME", "TRANSFER_IN"])
        )
    ) or 0.0
    expense = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "EXPENSE"
        )
    ) or 0.0
    deposits = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "DEPOSIT"
        )
    ) or 0.0
    transfers_out = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "TRANSFER_OUT"
        )
    ) or 0.0
    safe_drops = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "SAFE_DROP"
        )
    ) or 0.0
    sales_cash = await db.scalar(
        select(func.coalesce(func.sum(Dispatch.total), 0)).where(
            Dispatch.shift_id == shift_id,
            Dispatch.status == "COLLECTED",
        )
    ) or 0.0

    opening = Decimal(str(shift.opening_cash))
    result = opening + Decimal(str(income)) + Decimal(str(sales_cash)) - Decimal(str(expense)) - Decimal(str(deposits)) - Decimal(str(transfers_out)) - Decimal(str(safe_drops))
    return max(result, Decimal("0"))


@router.post("/cash-movements", response_model=CashMovementResponse, status_code=201)
async def create_cash_movement(
    body: CreateCashMovementRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Record a cash movement (income, expense, deposit)."""
    # Calculate running balance
    last = await db.execute(
        select(CashMovement)
        .where(CashMovement.shift_id == body.shift_id)
        .order_by(CashMovement.movement_id.desc())
        .limit(1)
    )
    last_mv = last.scalar_one_or_none()
    last_balance = Decimal(str(last_mv.running_balance)) if last_mv else Decimal("0")

    delta = Decimal(str(body.amount)) if body.type == "INCOME" else -Decimal(str(body.amount))
    running = last_balance + delta

    mv = CashMovement(
        shift_id=body.shift_id,
        type=body.type,
        amount=float(body.amount),
        observation=body.observation,
        running_balance=float(running),
    )
    db.add(mv)
    await db.commit()
    await db.refresh(mv)

    return CashMovementResponse(
        movement_id=mv.movement_id,
        shift_id=mv.shift_id,
        type=mv.type,
        amount=mv.amount,
        observation=mv.observation,
        created_at=mv.created_at,
        running_balance=mv.running_balance,
    )


@router.get("/shifts/{shift_id}/cash-movements", response_model=list[CashMovementResponse])
async def get_cash_movements(
    shift_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get all cash movements for a shift."""
    result = await db.execute(
        select(CashMovement)
        .where(CashMovement.shift_id == shift_id)
        .order_by(CashMovement.created_at.desc())
    )
    movements = result.scalars().all()
    return [
        CashMovementResponse(
            movement_id=m.movement_id,
            shift_id=m.shift_id,
            type=m.type,
            amount=m.amount,
            observation=m.observation,
            created_at=m.created_at,
            running_balance=m.running_balance,
        )
        for m in movements
    ]


@router.get("/cash-movements/{movement_id}")
async def get_cash_movement(
    movement_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get a single cash movement (for reprinting)."""
    result = await db.execute(
        select(CashMovement, Shift, User)
        .join(Shift, CashMovement.shift_id == Shift.shift_id)
        .join(User, Shift.user_id == User.user_id)
        .where(CashMovement.movement_id == movement_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    mv, shift, user = row
    return {
        "movement_id": mv.movement_id,
        "shift_id": mv.shift_id,
        "type": mv.type,
        "amount": mv.amount,
        "observation": mv.observation,
        "created_at": mv.created_at.isoformat() if mv.created_at else None,
        "running_balance": mv.running_balance,
        "user_name": user.name,
    }


@router.get("/shifts/{shift_id}/cash-summary", response_model=CashSummaryResponse)
async def get_cash_summary(
    shift_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get cash summary for a shift."""
    shift = (await db.execute(
        select(Shift).where(Shift.shift_id == shift_id)
    )).scalar_one_or_none()

    if not shift:
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    income = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type.in_(["INCOME", "TRANSFER_IN"])
        )
    ) or 0.0
    expense = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "EXPENSE"
        )
    ) or 0.0
    deposits = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "DEPOSIT"
        )
    ) or 0.0
    transfers_out = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "TRANSFER_OUT"
        )
    ) or 0.0
    safe_drops = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "SAFE_DROP"
        )
    ) or 0.0
    transfers_received = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "TRANSFER_IN"
        )
    ) or 0.0
    sales_cash = await db.scalar(
        select(func.coalesce(func.sum(Dispatch.total), 0)).where(
            Dispatch.shift_id == shift_id,
            Dispatch.status == "COLLECTED",
        )
    ) or 0.0

    opening = float(shift.opening_cash)
    # Cast all to float — Numeric columns return Decimal from asyncpg
    balance = opening + float(income or 0) + float(sales_cash or 0) - float(expense or 0) - float(deposits or 0) - float(transfers_out or 0) - float(safe_drops or 0)

    return CashSummaryResponse(
        shift_id=shift_id,
        opening_cash=opening,
        current_balance=round(balance, 2),
        total_income=round(income, 2),
        total_expense=round(expense, 2),
        total_deposits=round(deposits, 2),
        total_sales_cash=round(sales_cash, 2),
        total_transfers_received=round(transfers_received, 2),
        total_transfers_sent=round(transfers_out, 2),
        total_safe_drops=round(safe_drops, 2),
    )


@router.post("/transfers", response_model=TransferResponse, status_code=201)
async def create_transfer(
    body: CreateTransferRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Transfer money between users with open shifts."""

    from_shift = (await db.execute(
        select(Shift).where(Shift.shift_id == body.from_shift_id)
    )).scalar_one_or_none()

    if not from_shift:
        raise HTTPException(status_code=404, detail="Turno origen no encontrado")

    to_user = (await db.execute(
        select(User).where(User.user_id == body.to_user_id)
    )).scalar_one_or_none()
    if not to_user:
        raise HTTPException(status_code=404, detail="Usuario destino no encontrado")
    to_name = to_user.name

    # Verify target user has an open shift
    to_shift = (await db.execute(
        select(Shift).where(
            Shift.user_id == body.to_user_id,
            Shift.status == "OPEN",
        )
    )).scalar_one_or_none()
    if not to_shift:
        raise HTTPException(status_code=400, detail="El usuario destino no tiene un turno abierto")

    transfer = Transfer(
        from_shift_id=body.from_shift_id,
        to_user_id=body.to_user_id,
        to_user_name=to_name,
        amount=float(body.amount),
        observation=body.observation,
    )
    db.add(transfer)

    # Create TRANSFER_OUT for sender
    last = await db.execute(
        select(CashMovement)
        .where(CashMovement.shift_id == body.from_shift_id)
        .order_by(CashMovement.movement_id.desc())
        .limit(1)
    )
    last_mv = last.scalar_one_or_none()
    last_balance = float(last_mv.running_balance) if last_mv else 0.0

    mv = CashMovement(
        shift_id=body.from_shift_id,
        type="TRANSFER_OUT",
        amount=float(body.amount),
        observation=body.observation,
        related_user_id=body.to_user_id,
        related_user_name=to_name,
        running_balance=last_balance - float(body.amount),
    )
    db.add(mv)

    # Create INCOME movement for receiver
    to_shift_result = await db.execute(
        select(Shift).where(
            Shift.user_id == body.to_user_id,
            Shift.status == "OPEN",
        )
    )
    to_shift = to_shift_result.scalar_one_or_none()
    if to_shift:
        # Calculate receiver's running balance
        to_last = await db.execute(
            select(CashMovement)
            .where(CashMovement.shift_id == to_shift.shift_id)
            .order_by(CashMovement.movement_id.desc())
            .limit(1)
        )
        to_last_mv = to_last.scalar_one_or_none()
        to_last_balance = float(to_last_mv.running_balance) if to_last_mv else 0.0

        to_mv = CashMovement(
            shift_id=to_shift.shift_id,
            type="TRANSFER_IN",
            amount=float(body.amount),
            observation=f"Transferencia recibida de {from_shift.user_id}",
            related_user_id=from_shift.user_id,
            related_user_name=str(from_shift.user_id),
            running_balance=to_last_balance + float(body.amount),
        )
        db.add(to_mv)

    await db.commit()
    await db.refresh(transfer)

    return TransferResponse(
        transfer_id=transfer.transfer_id,
        from_shift_id=transfer.from_shift_id,
        from_user_name=str(from_shift.user_id),
        to_user_id=body.to_user_id,
        to_user_name=to_name,
        amount=transfer.amount,
        observation=transfer.observation,
        created_at=transfer.created_at,
    )


@router.get("/users/online", response_model=list[OnlineUserResponse])
async def get_users_online(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get all users with open shifts and their sales summary."""
    open_shifts = (await db.execute(
        select(Shift, User)
        .join(User, Shift.user_id == User.user_id)
        .where(Shift.status == "OPEN")
    )).all()

    online = []
    for shift, user in open_shifts:
        sales_count = await db.scalar(
            select(func.count()).where(
                Dispatch.shift_id == shift.shift_id,
                Dispatch.status == "COMPLETED",
            )
        ) or 0
        total_amount = await db.scalar(
            select(func.coalesce(func.sum(Dispatch.total), 0)).where(
                Dispatch.shift_id == shift.shift_id,
                Dispatch.status == "COMPLETED",
            )
        ) or 0

        online.append(OnlineUserResponse(
            user_id=user.user_id,
            name=user.name,
            role=user.role.code if user.role else "DISPATCHER",
            shift_id=shift.shift_id,
            sales_count=sales_count,
            total_amount=round(total_amount, 2),
        ))

    return online
