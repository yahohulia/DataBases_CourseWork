"""Pydantic-моделі запитів і відповідей (відображаються у Swagger UI)."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

RoleCode = Literal["student", "teacher", "admin"]
CourseStatus = Literal["draft", "published", "archived"]
MaterialType = Literal["video", "pdf", "link", "text"]
EnrollmentStatus = Literal["active", "completed", "dropped"]


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


def make_update(model: type[BaseModel], name: str) -> type[BaseModel]:
    """Модель часткового оновлення (PATCH): усі поля необов'язкові."""
    fields = {k: (Optional[v.annotation], None) for k, v in model.model_fields.items()}
    from pydantic import create_model
    return create_model(name, __base__=Base, **fields)


# ---------------- users ----------------
class UserCreate(Base):
    email: str = Field(..., max_length=120, examples=["new.student@elearn.test"])
    full_name: str = Field(..., max_length=150, examples=["Новий Студент Іванович"])
    role_code: RoleCode = "student"
    is_active: bool = True


class UserOut(UserCreate):
    id: int
    created_at: datetime


# ---------------- categories ----------------
class CategoryCreate(Base):
    name: str = Field(..., max_length=100, examples=["DevOps"])
    parent_id: Optional[int] = Field(None, examples=[1])


class CategoryOut(CategoryCreate):
    id: int


# ---------------- courses ----------------
class CourseCreate(Base):
    code: str = Field(..., pattern=r"^[A-Z]{2,6}-[0-9]{3}$", examples=["OPS-210"])
    title: str = Field(..., max_length=200, examples=["Основи DevOps"])
    description: Optional[str] = None
    category_id: int = Field(..., examples=[2])
    teacher_id: int = Field(..., examples=[4])
    status: CourseStatus = "draft"
    start_date: date = Field(..., examples=["2027-02-01"])
    end_date: date = Field(..., examples=["2027-05-31"])
    max_students: int = Field(30, ge=1, le=1000)


class CourseOut(CourseCreate):
    id: int
    created_at: datetime


# ---------------- modules ----------------
class ModuleCreate(Base):
    course_id: int = Field(..., examples=[1])
    title: str = Field(..., max_length=200, examples=["Резервне копіювання"])
    position: int = Field(..., gt=0, examples=[4])


class ModuleOut(ModuleCreate):
    id: int


# ---------------- materials ----------------
class MaterialCreate(Base):
    module_id: int = Field(..., examples=[3])
    title: str = Field(..., max_length=200, examples=["Документація pg_dump"])
    material_type: MaterialType = Field(..., examples=["link"])
    url: Optional[str] = Field(None, examples=["https://www.postgresql.org/docs/18/app-pgdump.html"])
    content: Optional[str] = None
    duration_min: Optional[int] = Field(None, gt=0)
    position: int = Field(..., gt=0, examples=[3])


class MaterialOut(MaterialCreate):
    id: int
    created_at: datetime


# ---------------- assignments ----------------
class AssignmentCreate(Base):
    module_id: int = Field(..., examples=[3])
    title: str = Field(..., max_length=200, examples=["Відновлення з дампу"])
    description: Optional[str] = None
    max_score: Decimal = Field(..., gt=0, le=100, examples=[20])
    due_at: datetime = Field(..., examples=["2026-12-10T23:59:00+02:00"])
    max_attempts: int = Field(3, ge=1, le=10)


class AssignmentOut(AssignmentCreate):
    id: int
    created_at: datetime


# ---------------- enrollments ----------------
class EnrollmentCreate(Base):
    course_id: int = Field(..., examples=[1])
    student_id: int = Field(..., examples=[16])


class EnrollmentUpdate(Base):
    status: Optional[EnrollmentStatus] = None


class EnrollmentOut(EnrollmentCreate):
    id: int
    enrolled_at: datetime
    status: EnrollmentStatus
    final_score: Optional[Decimal] = None
    completed_at: Optional[datetime] = None


# ---------------- submissions ----------------
class SubmissionCreate(Base):
    assignment_id: int = Field(..., examples=[3])
    enrollment_id: int = Field(..., examples=[7])
    answer_text: Optional[str] = Field(None, examples=["Seq Scan замінено на Index Scan"])
    answer_url: Optional[str] = None
    submitted_at: Optional[datetime] = Field(None, description="За замовчуванням — поточний момент")


class SubmissionUpdate(Base):
    answer_text: Optional[str] = None
    answer_url: Optional[str] = None
    status: Optional[Literal["submitted", "graded", "returned"]] = None


class SubmissionOut(Base):
    id: int
    assignment_id: int
    enrollment_id: int
    attempt_no: int
    answer_text: Optional[str] = None
    answer_url: Optional[str] = None
    submitted_at: datetime
    is_late: bool
    status: str


# ---------------- grades ----------------
class GradeCreate(Base):
    submission_id: int = Field(..., examples=[50])
    grader_id: int = Field(..., examples=[2])
    score: Decimal = Field(..., ge=0, examples=[18])
    feedback: Optional[str] = Field(None, examples=["Добрий аналіз плану"])


class GradeUpdate(Base):
    score: Optional[Decimal] = Field(None, ge=0)
    feedback: Optional[str] = None


class GradeOut(GradeCreate):
    id: int
    graded_at: datetime


# ---------------- material progress ----------------
class ProgressCreate(Base):
    enrollment_id: int = Field(..., examples=[1])
    material_id: int = Field(..., examples=[1])


class ProgressOut(ProgressCreate):
    first_viewed_at: datetime
    last_viewed_at: datetime
    views_count: int
