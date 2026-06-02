"""Unit tests for sequential_service."""

import pytest
from sqlalchemy import select

from app.models.tributary import EmissionPoint
from app.services.sequential_service import (
    SequentialExhaustedError,
    consume_sequential,
)


class TestConsumeSequential:
    @pytest.mark.asyncio
    async def test_consumes_first_number(self, db):
        seq = await consume_sequential(db, 1)
        assert seq == "001-001-000000001"

    @pytest.mark.asyncio
    async def test_increments_on_each_call(self, db):
        s1 = await consume_sequential(db, 1)
        s2 = await consume_sequential(db, 1)
        s3 = await consume_sequential(db, 1)
        assert s1 == "001-001-000000001"
        assert s2 == "001-001-000000002"
        assert s3 == "001-001-000000003"

    @pytest.mark.asyncio
    async def test_persists_between_transactions(self, db):
        await consume_sequential(db, 1)
        await db.commit()
        # New transaction should see the updated value
        seq = await consume_sequential(db, 1)
        assert seq == "001-001-000000002"

    @pytest.mark.asyncio
    async def test_exhausted_raises_error(self, db):
        ep = (await db.execute(select(EmissionPoint).where(EmissionPoint.emission_point_id == 1))).scalar_one()
        ep.current_sequential = 9999
        ep.sequential_end = 9999
        await db.flush()

        # Consume the last one
        seq = await consume_sequential(db, 1)
        assert seq == "001-001-000009999"

        # Now it should be exhausted
        with pytest.raises(SequentialExhaustedError) as exc:
            await consume_sequential(db, 1)
        assert "agotado" in str(exc.value).lower()
        assert "001-001" in str(exc.value)

    @pytest.mark.asyncio
    async def test_nonexistent_emission_point_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            await consume_sequential(db, 999)

    @pytest.mark.asyncio
    async def test_format_is_correct(self, db):
        seq = await consume_sequential(db, 1)
        parts = seq.split("-")
        assert len(parts) == 3
        assert parts[0] == "001"
        assert parts[1] == "001"
        assert len(parts[2]) == 9  # zero-padded
