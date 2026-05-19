# DB Migrations

Idempotent SQLite schema migrations. Each script guards with
`PRAGMA table_info` and is safe to run multiple times.

Database file: `data/cricket_intelligence.db` (path configurable via
`DATABASE_URL` env var, default
`sqlite:///./data/cricket_intelligence.db`).

## Migrations

### `migrate_add_pose.py`

```bash
python features/db_migrations/migrate_add_pose.py
```

Adds:
- `balls.pose_features` (TEXT, JSON) — per-ball MediaPipe feature dump
- `ground_truth` table — coach corrections feeding the continuous-learning
  flywheel. Columns: `id`, `ball_id`, `field_name`, `old_value`,
  `new_value`, `coach_id`, `timestamp`, `pose_features_snapshot`,
  `source`. Indexed on `ball_id` and `field_name`.

### `migrate_delivery_subtype.py`

```bash
python features/db_migrations/migrate_delivery_subtype.py
```

Adds (all default to `'unknown'`):
- `swing_direction` — `in_swing` / `out_swing` / `none` / `unknown`
- `swing_type` — `conventional` / `late` / `reverse` / `none` / `unknown`
- `spin_direction` — `off_break` / `leg_break` / `googly` / `arm_ball` / `doosra` / `carrom` / `top_spin` / `slider` / `none` / `unknown`
- `ball_age_phase` — `new_ball` / `old` / `reverse_window` / `unknown`

## When to run

After pulling new code that depends on these columns. Both scripts print
which columns they added (or skipped because they already exist).

## Note on flags

Neither script takes any flags — they connect to the path implied by
`DATABASE_URL`, run their `ALTER TABLE` statements, and exit.
