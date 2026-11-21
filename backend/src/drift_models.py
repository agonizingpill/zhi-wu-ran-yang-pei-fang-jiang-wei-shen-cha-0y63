from sqlalchemy import String,Float,Boolean,ForeignKey,JSON,UniqueConstraint,DateTime,func
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class DriftBaseline(Base):
    __tablename__='drift_baselines'
    __table_args__=(UniqueConstraint('recipe_id','version'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    recipe_id:Mapped[int]=mapped_column(ForeignKey('dye_recipes.id'))
    version:Mapped[int]=mapped_column()
    state:Mapped[str]=mapped_column(String(20),default='candidate')
    sample_ids:Mapped[list]=mapped_column(JSON)
    sample_lots:Mapped[list]=mapped_column(JSON)
    model:Mapped[dict]=mapped_column(JSON)
    explained_variance:Mapped[list]=mapped_column(JSON)
    recon_limit:Mapped[float]=mapped_column(Float)
    train_mse:Mapped[float]=mapped_column(Float)
    sample_count:Mapped[int]=mapped_column()
    retry_used:Mapped[bool]=mapped_column(Boolean,default=False)
    created_by:Mapped[str]=mapped_column(String(120),default='')
    created_at:Mapped[object]=mapped_column(DateTime,server_default=func.now())
class DriftReview(Base):
    __tablename__='drift_reviews'
    id:Mapped[int]=mapped_column(primary_key=True)
    swatch_id:Mapped[int]=mapped_column(ForeignKey('swatches.id'))
    recipe_id:Mapped[int]=mapped_column(ForeignKey('dye_recipes.id'))
    baseline_id:Mapped[int|None]=mapped_column(ForeignKey('drift_baselines.id'),nullable=True)
    baseline_version:Mapped[int|None]=mapped_column(nullable=True)
    projected_x:Mapped[float|None]=mapped_column(Float,nullable=True)
    projected_y:Mapped[float|None]=mapped_column(Float,nullable=True)
    recon_error:Mapped[float|None]=mapped_column(Float,nullable=True)
    drift_distance:Mapped[float|None]=mapped_column(Float,nullable=True)
    level:Mapped[str]=mapped_column(String(20))
    state:Mapped[str]=mapped_column(String(24),default='projected')
    block_reason:Mapped[str]=mapped_column(String(400),default='')
    sample_lots:Mapped[list]=mapped_column(JSON)
    decided_by:Mapped[str]=mapped_column(String(120),default='')
    decided_at:Mapped[object|None]=mapped_column(DateTime,nullable=True)
    created_at:Mapped[object]=mapped_column(DateTime,server_default=func.now())
