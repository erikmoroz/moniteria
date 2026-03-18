"""Business logic for the categories app."""

from __future__ import annotations

from django.db import IntegrityError

from categories.exceptions import (
    CategoryDuplicateNameError,
    CategoryNotFoundError,
    CategoryPeriodNotFoundError,
)
from categories.models import Category
from categories.schemas import CategoryCreate, CategoryUpdate
from common.services.base import get_workspace_period


class CategoryService:
    @staticmethod
    def get_category(category_id: int, workspace_id: int) -> Category:
        """Get a category and verify it belongs to the workspace."""
        category = (
            Category.objects.select_related('budget_period__budget_account')
            .filter(id=category_id, budget_period__budget_account__workspace_id=workspace_id)
            .first()
        )
        if not category:
            raise CategoryNotFoundError()
        return category

    @staticmethod
    def list(workspace_id: int, budget_period_id: int | None = None, current_date=None) -> list[Category]:
        """List categories for a workspace, optionally filtered by period or date.

        Returns an empty list (not 404) when budget_period_id does not belong to
        the workspace. This prevents leaking whether a period ID exists elsewhere.
        """
        from budget_periods.models import BudgetPeriod

        if current_date and not budget_period_id:
            period = (
                BudgetPeriod.objects.select_related('budget_account')
                .for_workspace(workspace_id)
                .filter(start_date__lte=current_date, end_date__gte=current_date)
                .first()
            )
            if period:
                budget_period_id = period.id
            else:
                return []

        if budget_period_id is None:
            return []

        period = get_workspace_period(budget_period_id, workspace_id)
        if not period:
            return []

        return list(Category.objects.filter(budget_period_id=budget_period_id))

    @staticmethod
    def create(user, workspace_id: int, data: CategoryCreate) -> Category:
        """Create a category, validating period ownership."""
        period = get_workspace_period(data.budget_period_id, workspace_id)
        if not period:
            raise CategoryPeriodNotFoundError()

        try:
            return Category.objects.create(
                budget_period_id=data.budget_period_id,
                name=data.name,
                created_by=user,
                updated_by=user,
            )
        except IntegrityError:
            raise CategoryDuplicateNameError()

    @staticmethod
    def update(user, workspace_id: int, category_id: int, data: CategoryUpdate) -> Category:
        """Update a category."""
        category = CategoryService.get_category(category_id, workspace_id)

        if data.name is not None:
            category.name = data.name

        category.updated_by = user
        category.save()

        return category

    @staticmethod
    def delete(user, workspace_id: int, category_id: int) -> None:
        """Delete a category."""
        category = CategoryService.get_category(category_id, workspace_id)
        category.delete()

    @staticmethod
    def export(workspace_id: int, period_id: int) -> list[str]:
        """Return category names for a period."""
        period = get_workspace_period(period_id, workspace_id)
        if not period:
            raise CategoryPeriodNotFoundError()

        return list(Category.objects.filter(budget_period_id=period_id).values_list('name', flat=True))

    @staticmethod
    def import_data(user, workspace_id: int, period_id: int, data: list) -> int:
        """Bulk-create categories from a list of name strings. Returns count of created records."""
        period = get_workspace_period(period_id, workspace_id)
        if not period:
            raise CategoryPeriodNotFoundError()

        existing_names = set(Category.objects.filter(budget_period_id=period_id).values_list('name', flat=True))

        new_categories = []
        for name in data:
            if name not in existing_names:
                new_categories.append(Category(name=name, budget_period_id=period_id, created_by=user, updated_by=user))
                existing_names.add(name)

        if not new_categories:
            return 0

        Category.objects.bulk_create(new_categories)
        return len(new_categories)
