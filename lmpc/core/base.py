from abc import ABC, abstractmethod
from typing import (
    Any,
    Iterator, 
    Generator,
    AsyncGenerator, 
    TypedDict,
    override,
)


_Metrics = dict[str, int | float | str | list[int] | list[float] | list[str]]


class BaseDataModule(ABC):
    """Base data module class for handling data loading and preprocessing."""

    @override
    def preprocess(self, data: Any) -> Any:
        """Preprocess the input data.

        Args:
            data (Any): Raw input data to preprocess.

        Returns:
            Any: Preprocessed data.
        """
        return data

    @abstractmethod
    def __getitem__(self, index: int | slice[int, int, int]) -> Any:
        """Retrieve a data sample by index.

        Args:
            index (int | slice): Index or slice of the data samples to retrieve.

        Returns:
            Any: The data sample corresponding to the given index.
        """
        raise NotImplementedError
    
    @abstractmethod
    def __len__(self) -> int:
        """Get the total number of data samples.

        Returns:
            int: Total number of data samples.
        """
        raise NotImplementedError
    
    @abstractmethod
    def __iter__(self) -> Iterator[Any]:
        """Create an iterator over the data samples.

        Returns:
            Iterator: An iterator over the data samples.
        """
        raise NotImplementedError


class BasePlatformModule(ABC):
    """Base platform module class for handling platform-specific operations."""

    @abstractmethod
    def request(self, data: Any) -> Any:
        """Make a platform-specific request.

        Args:
            data (Any): Data to send in the request.

        Returns:
            Any: Response from the platform.
        """
        raise NotImplementedError
    
    @abstractmethod
    async def arequest(self, data: Any) -> Any:
        """Make an asynchronous platform-specific request.

        Args:
            data (Any): Data to send in the request.

        Returns:
            Any: Response from the platform.
        """
        raise NotImplementedError
    
    @abstractmethod
    def stream(self, data: Any) -> Generator[Any, None, None]:
        """Stream data from the platform.

        Args:
            data (Any): Data to send in the streaming request.

        Yields:
            Any: Streamed data from the platform.
        """
        raise NotImplementedError

    @abstractmethod
    async def astream(self, data: Any) -> AsyncGenerator[Any, None]:
        """Asynchronously stream data from the platform.

        Args:
            data (Any): Data to send in the streaming request.

        Yields:
            Any: Streamed data from the platform.
        """
        raise NotImplementedError
    

class BaseTestModule(ABC):
    """Base test module class for handling testing operations."""

    @abstractmethod
    def before_request(self, data: Any) -> None:
        """Hook to run before making a request.

        Args:
            data (Any): Data to be sent in the request.
        """
        raise NotImplementedError
    
    @abstractmethod
    def during_request(self, data: Any) -> None:
        """Hook to run during the request process.

        Args:
            data (Any): Data being sent in the request.
        """
        raise NotImplementedError
    
    @abstractmethod
    def after_request(self, response: Any) -> None:
        """Hook to run after receiving a response.

        Args:
            response (Any): Response received from the request.
        """
        raise NotImplementedError
    
    @abstractmethod
    def on_error(self, error: Exception) -> None:
        """Hook to run when an error occurs.

        Args:
            error (Exception): The exception that occurred.
        """
        raise NotImplementedError
    
    @abstractmethod
    def on_complete(self) -> _Metrics:
        """Hook to run when all tests are complete.

        Returns:
            _Metrics: A dictionary of metrics collected during testing.
        """
        raise NotImplementedError