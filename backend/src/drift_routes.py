from fastapi import APIRouter,Depends
from sqlalchemy import select
from .database import session
from .auth import current,editor,admin
from .drift_models import DriftBaseline,DriftReview
from .drift_schemas import BaselineRebuildInput,ProjectInput,ConfirmInput
from . import drift_service
router=APIRouter()
@router.get('/drift/baselines')
def baselines(user=Depends(current),db=Depends(session)):return db.scalars(select(DriftBaseline).order_by(DriftBaseline.id.desc())).all()
@router.post('/drift/baselines/rebuild')
def rebuild(data:BaselineRebuildInput,user=Depends(editor),db=Depends(session)):return drift_service.rebuild_baseline(db,data,user)
@router.post('/drift/baselines/{key}/activate')
def activate(key:int,user=Depends(editor),db=Depends(session)):return drift_service.switch_baseline(db,key,user)
@router.get('/drift/reviews')
def reviews(user=Depends(current),db=Depends(session)):return db.scalars(select(DriftReview).order_by(DriftReview.id.desc())).all()
@router.post('/drift/project')
def project(data:ProjectInput,user=Depends(editor),db=Depends(session)):return drift_service.project_swatch(db,data,user)
@router.post('/drift/reviews/{key}/confirm')
def confirm(key:int,data:ConfirmInput,user=Depends(admin),db=Depends(session)):return drift_service.confirm_review(db,key,data,user)
