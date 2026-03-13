from app.extensions import db
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
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
        return db.session.get(self.model, id)

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
        try:
            db.session.commit()
            return entity
        except IntegrityError as exc:
            db.session.rollback()

            # Recovery path for PostgreSQL sequence drift (id sequence behind MAX(id)).
            if self._is_postgres_pk_conflict(exc):
                if self._resync_pk_sequence():
                    db.session.add(entity)
                    db.session.commit()
                    return entity

            raise

    def _is_postgres_pk_conflict(self, exc: IntegrityError) -> bool:
        bind = db.session.get_bind()
        if not bind or bind.dialect.name != 'postgresql':
            return False

        if not hasattr(self.model, '__table__'):
            return False

        pk_columns = list(self.model.__mapper__.primary_key)
        if len(pk_columns) != 1:
            return False

        pk_col = pk_columns[0].name
        if pk_col != 'id':
            return False

        message = str(getattr(exc, 'orig', exc)).lower()
        return ('_pkey' in message) and ('duplicate' in message or 'duplicar valor da chave' in message)

    def _resync_pk_sequence(self) -> bool:
        bind = db.session.get_bind()
        if not bind or bind.dialect.name != 'postgresql':
            return False

        table_name = self.model.__table__.name
        pk_col = self.model.__mapper__.primary_key[0].name

        seq_name = db.session.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :pk_col)"),
            {'table_name': table_name, 'pk_col': pk_col},
        ).scalar()

        if not seq_name:
            return False

        db.session.execute(
            text(
                f'SELECT setval(CAST(:seq_name AS regclass), '
                f'COALESCE((SELECT MAX("{pk_col}") FROM "{table_name}"), 0) + 1, false)'
            ),
            {'seq_name': seq_name},
        )
        db.session.commit()
        return True

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
