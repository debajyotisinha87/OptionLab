# Project Rules

## Coding Rules

- Use Python 3.14+
- Use type hints.
- Use dataclasses for models.
- No SQL outside Repository.
- No hardcoded credentials.
- No business logic inside API classes.
- All database access goes through Repository.

---

## Folder Rules

API logic

```
app/api
```

Database

```
app/database
```

Models

```
app/models
```

Business logic

```
app/services
```

Validation

```
app/validator
```

Planning

```
app/planner
```

---

## Git

Commit frequently.

Small commits.

Meaningful commit messages.

---

## Documentation

Every public class should have a docstring.

Every public method should have a docstring.