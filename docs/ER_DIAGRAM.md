# Database diagram

Generated from the SQLAlchemy models by `python scripts/make_er_diagram.py`, so it always matches the code.

![ER diagram](er-diagram.png)

## Interactive version 
```mermaid
erDiagram
  USERS ||--o{ USERS : "manager_id"
  USERS ||--o{ ACTIVITIES : "updated_by_id"
  USERS ||--o{ ACTIVITIES : "created_by_id"
  USERS ||--o{ ACTIVITIES : "owner_id"
  ACTIVITIES ||--o{ STATUS_HISTORY : "activity_id"
  USERS ||--o{ STATUS_HISTORY : "changed_by_id"
  USERS {
    uuid id PK
    varchar_120 full_name
    varchar_254 email UK
    varchar_20 phone
    varchar_255 password_hash
    user_role role
    uuid manager_id FK
    varchar_80 designation
    varchar_80 region
    varchar_30 employee_code UK
    boolean is_active
    boolean must_change_password
    int failed_login_attempts
    timestamptz locked_until
    timestamptz last_login_at
    timestamptz created_at
    timestamptz updated_at
  }
  ACTIVITIES {
    uuid id PK
    uuid owner_id FK
    varchar_120 customer_name
    varchar_120 customer_key
    activity_type activity_type
    activity_status status
    product product_interested
    varchar_20 contact
    varchar_120 location
    text notes
    date start_date
    date end_date
    date follow_up_date
    varchar_500 follow_up_notes
    uuid created_by_id FK
    uuid updated_by_id FK
    timestamptz created_at
    timestamptz updated_at
  }
  STATUS_HISTORY {
    uuid id PK
    uuid activity_id FK
    uuid changed_by_id FK
    activity_status from_status
    activity_status to_status
    timestamptz changed_at
  }
```



## Reading the diagram

- **users**: every employee. `manager_id` points to another user (who they report to).
- **activities**: one row per sales activity. `owner_id` is the salesperson it belongs to.
- **status_history**: audit trail of every status change (who, from, to, when).
- All IDs are UUIDs, so they can't be guessed or used to count records.
- Enums are real database enum types: `user_role`, `activity_type`, `activity_status`, `product`.
- A unique rule on (owner, customer, type, start date) prevents duplicate activities.
