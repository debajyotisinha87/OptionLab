from app.database.repository import Repository

repo = Repository()

repo.execute_sql_file("download_jobs.sql")

tables = repo.query("SHOW TABLES")

print(tables)