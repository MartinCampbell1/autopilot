"""Dispatcher for allocating workers and critics across multiple projects."""

from __future__ import annotations

from dataclasses import dataclass

from autopilot.core.models import ProjectConfig

PRIORITY_WEIGHTS = {
    "high": 3,
    "normal": 2,
    "low": 1,
}


@dataclass
class ProjectAllocation:
    project_name: str
    project_path: str
    worker_count: int
    critic_count: int
    priority: str


class Dispatcher:
    """Allocate worker and critic slots by project priority."""

    def __init__(self, total_workers: int = 14, total_critics: int = 5):
        self.total_workers = total_workers
        self.total_critics = total_critics

    def allocate(self, projects: list[ProjectConfig]) -> list[ProjectAllocation]:
        """Distribute workers and critics proportionally across projects."""
        if not projects:
            return []

        weights = [PRIORITY_WEIGHTS.get(project.priority, 2) for project in projects]
        total_weight = sum(weights)

        worker_counts = self._distribute(self.total_workers, weights, total_weight, len(projects))
        critic_counts = self._distribute(self.total_critics, weights, total_weight, len(projects))

        return [
            ProjectAllocation(
                project_name=project.name,
                project_path=project.path,
                worker_count=worker_counts[index],
                critic_count=critic_counts[index],
                priority=project.priority,
            )
            for index, project in enumerate(projects)
        ]

    def _distribute(self, total: int, weights: list[int], total_weight: int, count: int) -> list[int]:
        """Distribute slots by priority weight while giving each project at least one."""
        result = [1] * count
        remaining = total - count

        if remaining <= 0:
            return result

        for index, weight in enumerate(weights):
            share = int(remaining * weight / total_weight)
            result[index] += share

        distributed = sum(result)
        leftover = total - distributed
        sorted_indices = sorted(range(len(weights)), key=lambda idx: weights[idx], reverse=True)
        for index in range(leftover):
            result[sorted_indices[index % len(sorted_indices)]] += 1

        return result
