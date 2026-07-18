from abc import ABC, abstractmethod

from app.engine.result import EngineResult


class Engine(ABC):

    @abstractmethod
    def run_once(self) -> EngineResult:
        pass