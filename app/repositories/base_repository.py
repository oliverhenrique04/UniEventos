from app.extensions import db
from typing import Type, TypeVar, Generic, List, Optional

T = TypeVar('T')

class BaseRepository(Generic[T]):
    """Base Repository providing common database operations using SQLAlchemy.
    
    This class implements the Repository Pattern to abstract data access logic 
    from business services, promoting testability and clean architecture.
    """
    def __init__(self, model: Type[T]):
        """Initializes the repository with a specific model.
        
        Args:
            model (Type[T]): The SQLAlchemy model class to wrap.
        """
        self.model = model

    def get_by_id(self, id) -> Optional[T]:
        """Retrieves an entity by its primary key identifier.
        
        Args:
            id: The primary key value.
            
        Returns:
            Optional[T]: The found entity or None.
        """
        return self.model.query.get(id)

    def get_all(self) -> List[T]:
        """Retrieves all existing records for this entity.
        
        Returns:
            List[T]: A list of all entities in the database.
        """
        return self.model.query.all()

    def find_by(self, **kwargs) -> List[T]:
        """Filters entities based on provided keyword arguments.
        
        Args:
            **kwargs: Column names and values to filter by.
            
        Returns:
            List[T]: A list of matching entities.
        """
        return self.model.query.filter_by(**kwargs).all()

    def find_one_by(self, **kwargs) -> Optional[T]:
        """Finds a single entity matching the given criteria.
        
        Args:
            **kwargs: Column names and values to filter by.
            
        Returns:
            Optional[T]: The first matching entity or None.
        """
        return self.model.query.filter_by(**kwargs).first()

    def save(self, entity: T) -> T:
        """Persists a new or updated entity to the database.
        
        Args:
            entity (T): The entity instance to save.
            
        Returns:
            T: The saved entity with updated state (e.g., auto-incremented ID).
        """
        db.session.add(entity)
        db.session.commit()
        return entity

    def delete(self, entity: T) -> None:
        """Permanently removes an entity from the database.
        
        Args:
            entity (T): The entity instance to delete.
        """
        db.session.delete(entity)
        db.session.commit()

    def update(self) -> None:
        """Flushes and commits current session changes to the database.
        
        This is useful for tracking changes to already attached entities.
        """
        db.session.commit()
