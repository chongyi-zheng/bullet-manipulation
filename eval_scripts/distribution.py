import abc
from typing import Dict
from gym import Space


class DictDistribution(object, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def sample(self, batch_size: int):
        pass

    @property
    @abc.abstractmethod
    def spaces(self) -> Dict[str, Space]:
        pass

    def __call__(self, *args, **kwargs):
        """For backward compatibility with DictDistributionGenerator"""
        return self
