from app.database.repository import Repository

repo = Repository()

tables = repo.query(
    """
    SHOW TABLES
    """
)

print(tables)
