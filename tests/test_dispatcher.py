"""Tests for multi-project dispatcher."""

from autopilot.core.dispatcher import Dispatcher
from autopilot.core.models import ProjectConfig


class TestDispatcher:
    def test_allocate_single_project(self) -> None:
        projects = [ProjectConfig(name="proj-a", path="/tmp/a", priority="normal")]
        dispatcher = Dispatcher(total_workers=14, total_critics=5)
        allocations = dispatcher.allocate(projects)

        assert len(allocations) == 1
        assert allocations[0].worker_count == 14
        assert allocations[0].critic_count == 5

    def test_allocate_by_priority(self) -> None:
        projects = [
            ProjectConfig(name="proj-high", path="/tmp/a", priority="high"),
            ProjectConfig(name="proj-normal", path="/tmp/b", priority="normal"),
            ProjectConfig(name="proj-low", path="/tmp/c", priority="low"),
        ]
        dispatcher = Dispatcher(total_workers=14, total_critics=5)
        allocations = dispatcher.allocate(projects)

        high = next(item for item in allocations if item.project_name == "proj-high")
        normal = next(item for item in allocations if item.project_name == "proj-normal")
        low = next(item for item in allocations if item.project_name == "proj-low")

        assert high.worker_count >= normal.worker_count
        assert normal.worker_count >= low.worker_count

    def test_allocate_equal_priority(self) -> None:
        projects = [
            ProjectConfig(name="a", path="/tmp/a", priority="normal"),
            ProjectConfig(name="b", path="/tmp/b", priority="normal"),
        ]
        dispatcher = Dispatcher(total_workers=10, total_critics=4)
        allocations = dispatcher.allocate(projects)

        assert allocations[0].worker_count == 5
        assert allocations[1].worker_count == 5

    def test_every_project_gets_at_least_one(self) -> None:
        projects = [
            ProjectConfig(name=f"p{i}", path=f"/tmp/p{i}", priority="normal")
            for i in range(10)
        ]
        dispatcher = Dispatcher(total_workers=14, total_critics=5)
        allocations = dispatcher.allocate(projects)

        for allocation in allocations:
            assert allocation.worker_count >= 1
            assert allocation.critic_count >= 1
