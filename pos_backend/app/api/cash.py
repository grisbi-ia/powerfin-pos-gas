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


@router.post("/cash-movements", response_model=CashMovementResponse, status_code=201)
async def create_cash_movement(
    body: CreateCashMovementRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Record a cash movement (income or expense)."""
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
            CashMovement.shift_id == shift_id, CashMovement.type == "INCOME"
        )
    ) or 0.0
    expense = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "EXPENSE"
        )
    ) or 0.0
    sales_cash = await db.scalar(
        select(func.coalesce(func.sum(Dispatch.total), 0)).where(
            Dispatch.shift_id == shift_id, Dispatch.status == "COLLECTED"
        )
    ) or 0.0

    opening = float(shift.opening_cash)
    balance = opening + float(income or 0) + float(sales_cash or 0) - float(expense or 0)

    return CashSummaryResponse(
        shift_id=shift_id,
        opening_cash=opening,
        current_balance=round(balance, 2),
        total_income=round(income, 2),
        total_expense=round(expense, 2),
        total_sales_cash=round(sales_cash, 2),
    )


@router.post("/transfers", response_model=TransferResponse, status_code=201)
async def create_transfer(
    body: CreateTransferRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Transfer money between users or to Caja Fuerte (to_user_id=0)."""
    from_shift = (await db.execute(
        select(Shift).where(Shift.shift_id == body.from_shift_id)
    )).scalar_one_or_none()

    if not from_shift:
        raise HTTPException(status_code=404, detail="Turno origen no encontrado")

    # Determine recipient name
    to_name = "Caja Fuerte" if body.to_user_id == 0 else "Despachador"
    if body.to_user_id != 0:
        to_user = (await db.execute(
            select(User).where(User.user_id == body.to_user_id)
        )).scalar_one_or_none()
        if to_user:
            to_name = to_user.name

    transfer = Transfer(
        from_shift_id=body.from_shift_id,
        to_user_id=body.to_user_id if body.to_user_id != 0 else None,
        to_user_name=to_name,
        amount=float(body.amount),
        observation=body.observation,
    )
    db.add(transfer)

    # Create cash movement for sender
    mv_type = "SAFE_DROP" if body.to_user_id == 0 else "TRANSFER_OUT"
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
        type=mv_type,
        amount=float(body.amount),
        observation=body.observation,
        related_user_id=body.to_user_id if body.to_user_id != 0 else None,
        related_user_name=to_name,
        running_balance=last_balance - float(body.amount),
    )
    db.add(mv)
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

    # Add Caja Fuerte
    online.append(OnlineUserResponse(
        user_id=0,
        name="Caja Fuerte",
        role="SAFE_VAULT",
        shift_id=0,
        sales_count=0,
        total_amount=0,
    ))

    return online
