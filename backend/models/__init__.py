"""ORM models — import all models so Base.metadata knows every table."""

from database import Base  # noqa: F401

from models.cluster import Cluster  # noqa: F401
from models.shift_report import ShiftReport  # noqa: F401
from models.daily_section import DailySection  # noqa: F401
from models.alert_record import AlertRecord, alert_record_labels  # noqa: F401
from models.label import Label  # noqa: F401
from models.weekly_task import WeeklyTask, ReportTaskAssignment  # noqa: F401
from models.filter_rule import AlertFilterRule  # noqa: F401
from models.maintenance_window import MaintenanceWindow  # noqa: F401
from models.poller_config import PollerConfig  # noqa: F401
from models.retention_config import RetentionConfig  # noqa: F401
