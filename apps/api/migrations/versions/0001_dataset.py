"""Initial dataset storage.

Revision ID: 0001_dataset
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_dataset"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('dataset_state',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('as_of_date', sa.Date(), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('source_meta', sa.JSON(), nullable=False),
    sa.Column('proficiency_scale', sa.JSON(), nullable=False),
    sa.CheckConstraint('id = 1'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('events',
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('format', sa.String(), nullable=False),
    sa.Column('duration_hours', sa.Float(), nullable=False),
    sa.Column('mandatory', sa.Boolean(), nullable=False),
    sa.Column('repeatable', sa.Boolean(), nullable=False),
    sa.Column('target_roles', sa.JSON(), nullable=False),
    sa.Column('target_grades', sa.JSON(), nullable=False),
    sa.Column('upcoming_sessions', sa.JSON(), nullable=False),
    sa.CheckConstraint("format IN ('online', 'offline', 'self_paced')"),
    sa.CheckConstraint('duration_hours > 0'),
    sa.PrimaryKeyConstraint('event_id')
    )
    op.create_table('role_grades',
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('grade', sa.String(), nullable=False),
    sa.Column('next_grade', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['role', 'next_grade'], ['role_grades.role', 'role_grades.grade'], ),
    sa.PrimaryKeyConstraint('role', 'grade')
    )
    op.create_table('skills',
    sa.Column('skill_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('category', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.CheckConstraint("type IN ('hard', 'soft')"),
    sa.PrimaryKeyConstraint('skill_id')
    )
    op.create_table('employees',
    sa.Column('employee_id', sa.String(), nullable=False),
    sa.Column('full_name', sa.String(), nullable=False),
    sa.Column('department', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('grade', sa.String(), nullable=False),
    sa.Column('manager_id', sa.String(), nullable=True),
    sa.Column('hire_date', sa.Date(), nullable=False),
    sa.Column('tenure_months', sa.Integer(), nullable=False),
    sa.Column('work_format', sa.String(), nullable=False),
    sa.Column('preferred_language', sa.String(), nullable=False),
    sa.Column('career_goal', sa.JSON(), nullable=True),
    sa.Column('last_review_date', sa.Date(), nullable=False),
    sa.CheckConstraint("preferred_language IN ('ru', 'kk', 'en')"),
    sa.CheckConstraint("work_format IN ('office', 'hybrid', 'remote')"),
    sa.CheckConstraint('tenure_months >= 0'),
    sa.ForeignKeyConstraint(['manager_id'], ['employees.employee_id'], ),
    sa.ForeignKeyConstraint(['role', 'grade'], ['role_grades.role', 'role_grades.grade'], ),
    sa.PrimaryKeyConstraint('employee_id')
    )
    op.create_table('event_prerequisites',
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('skill_id', sa.String(), nullable=False),
    sa.Column('required_level', sa.Integer(), nullable=False),
    sa.CheckConstraint('required_level BETWEEN 0 AND 5'),
    sa.ForeignKeyConstraint(['event_id'], ['events.event_id'], ),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id'], ),
    sa.PrimaryKeyConstraint('event_id', 'skill_id')
    )
    op.create_table('event_skills',
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('skill_id', sa.String(), nullable=False),
    sa.Column('gain', sa.Integer(), nullable=False),
    sa.Column('max_level', sa.Integer(), nullable=False),
    sa.CheckConstraint('gain BETWEEN 0 AND 5'),
    sa.CheckConstraint('max_level BETWEEN 0 AND 5'),
    sa.ForeignKeyConstraint(['event_id'], ['events.event_id'], ),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id'], ),
    sa.PrimaryKeyConstraint('event_id', 'skill_id')
    )
    op.create_table('grade_requirements',
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('grade', sa.String(), nullable=False),
    sa.Column('skill_id', sa.String(), nullable=False),
    sa.Column('required_level', sa.Integer(), nullable=False),
    sa.Column('critical', sa.Boolean(), nullable=False),
    sa.CheckConstraint('required_level BETWEEN 0 AND 5'),
    sa.ForeignKeyConstraint(['role', 'grade'], ['role_grades.role', 'role_grades.grade'], ),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id'], ),
    sa.PrimaryKeyConstraint('role', 'grade', 'skill_id')
    )
    op.create_table('activity_history',
    sa.Column('record_id', sa.String(), nullable=False),
    sa.Column('employee_id', sa.String(), nullable=False),
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('completion_pct', sa.Integer(), nullable=False),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('feedback_rating', sa.Integer(), nullable=True),
    sa.Column('assigned_by', sa.String(), nullable=False),
    sa.Column('effects_applied', sa.Boolean(), nullable=False),
    sa.CheckConstraint("assigned_by IN ('self', 'manager', 'hr')"),
    sa.CheckConstraint("status IN ('completed', 'in_progress', 'dropped', 'no_show', 'declined', 'overdue')"),
    sa.CheckConstraint('completion_pct BETWEEN 0 AND 100'),
    sa.CheckConstraint('feedback_rating BETWEEN 1 AND 5'),
    sa.CheckConstraint('score BETWEEN 0 AND 100'),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.employee_id'], ),
    sa.ForeignKeyConstraint(['event_id'], ['events.event_id'], ),
    sa.PrimaryKeyConstraint('record_id')
    )
    op.create_index(op.f('ix_activity_history_employee_id'), 'activity_history', ['employee_id'], unique=False)
    op.create_index(op.f('ix_activity_history_event_id'), 'activity_history', ['event_id'], unique=False)
    op.create_table('employee_skills',
    sa.Column('employee_id', sa.String(), nullable=False),
    sa.Column('skill_id', sa.String(), nullable=False),
    sa.Column('assessed_level', sa.Integer(), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.CheckConstraint('assessed_level BETWEEN 0 AND 5'),
    sa.CheckConstraint('level BETWEEN 0 AND 5'),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.employee_id'], ),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id'], ),
    sa.PrimaryKeyConstraint('employee_id', 'skill_id')
    )

def downgrade():
    op.drop_table('employee_skills')
    op.drop_index(op.f('ix_activity_history_event_id'), table_name='activity_history')
    op.drop_index(op.f('ix_activity_history_employee_id'), table_name='activity_history')
    op.drop_table('activity_history')
    op.drop_table('grade_requirements')
    op.drop_table('event_skills')
    op.drop_table('event_prerequisites')
    op.drop_table('employees')
    op.drop_table('skills')
    op.drop_table('role_grades')
    op.drop_table('events')
    op.drop_table('dataset_state')
