from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import select,func
from .models import DyeRecipe,Swatch,Trial
from .drift_models import DriftBaseline,DriftReview
from .atlas import fit_baseline,project_sample,drift_level
from .recipe_service import log,require

def released_swatches(db,recipe_id):
    trials=db.scalars(select(Trial).where(Trial.recipe_id==recipe_id,Trial.state=='approved')).all()
    ids={t.reference_swatch_id for t in trials}|{t.candidate_swatch_id for t in trials}
    ids|=set(db.scalars(select(DriftReview.swatch_id).where(DriftReview.recipe_id==recipe_id,DriftReview.state=='confirmed_normal')).all())
    if not ids:return []
    return db.scalars(select(Swatch).where(Swatch.id.in_(ids)).order_by(Swatch.id)).all()

def rebuild_baseline(db,data,user):
    recipe=require(db,DyeRecipe,data.recipe_id)
    pending=db.scalar(select(DriftBaseline).where(DriftBaseline.recipe_id==recipe.id,DriftBaseline.state=='candidate'))
    if pending:raise HTTPException(409,f'存在待切换基线 v{pending.version}，请先完成切换重试')
    pool=released_swatches(db,recipe.id)
    if len(pool)<3:raise HTTPException(409,f'已放行染样仅 {len(pool)} 张，不足 3 张，无法建立基线')
    fitted=fit_baseline([{'id':s.id,'lot':s.lot,'spectrum':s.spectrum} for s in pool])
    version=(db.scalar(select(func.max(DriftBaseline.version)).where(DriftBaseline.recipe_id==recipe.id))or 0)+1
    candidate=DriftBaseline(recipe_id=recipe.id,version=version,state='candidate',sample_ids=[s.id for s in pool],
        sample_lots=[s.lot for s in pool],model=fitted['model'],explained_variance=fitted['explained_variance'],
        recon_limit=fitted['recon_limit'],train_mse=fitted['train_mse'],sample_count=len(pool),created_by=user.email)
    db.add(candidate);log(db,user,f'构建基线 {recipe.code} v{version} 参与样本{len(pool)}张');db.commit()
    switch_baseline(db,candidate.id,user)
    db.refresh(candidate);return candidate

def switch_baseline(db,key,user):
    candidate=db.get(DriftBaseline,key)
    if not candidate:raise HTTPException(404,'基线版本不存在')
    if candidate.state!='candidate':raise HTTPException(409,'该基线版本已处理，切换只生效一次')
    recipe_id,version=candidate.recipe_id,candidate.version
    try:
        db.scalar(select(DyeRecipe).where(DyeRecipe.id==recipe_id).with_for_update())
        current=db.scalar(select(DriftBaseline).where(DriftBaseline.recipe_id==recipe_id,DriftBaseline.state=='active'))
        if current:current.state='superseded'
        candidate.state='active';db.commit()
    except Exception:
        db.rollback()
        try:
            fresh=db.get(DriftBaseline,key)
            if fresh.retry_used:
                fresh.state='failed';db.commit()
                raise HTTPException(502,'基线切换重试仍失败，该版本已作废；旧版本继续裁决')
            fresh.retry_used=True;db.commit()
            raise HTTPException(502,'基线切换失败，已保留旧版本；可重试一次')
        except HTTPException:raise
        except Exception:
            db.rollback();raise HTTPException(502,'基线切换失败，旧版本继续裁决；请稍后重试')
    try:
        log(db,user,f'基线切换至 v{version}，旧版留存备查');db.commit()
    except Exception:db.rollback()
    return candidate

def project_swatch(db,data,user):
    swatch=require(db,Swatch,data.swatch_id)
    anomaly=db.scalar(select(DriftReview).where(DriftReview.swatch_id==swatch.id,DriftReview.state=='confirmed_anomaly'))
    if anomaly:return anomaly
    db.scalar(select(DyeRecipe).where(DyeRecipe.id==swatch.recipe_id).with_for_update())
    baseline=db.scalar(select(DriftBaseline).where(DriftBaseline.recipe_id==swatch.recipe_id,DriftBaseline.state=='active'))
    existing=db.scalar(select(DriftReview).where(DriftReview.swatch_id==swatch.id,DriftReview.baseline_id==(baseline.id if baseline else None)))
    if existing:return existing
    if not baseline:
        review=DriftReview(swatch_id=swatch.id,recipe_id=swatch.recipe_id,baseline_id=None,baseline_version=None,
            level='pending_review',state='pending_review',sample_lots=[],
            block_reason='该配方尚无有效降维基线（已放行染样不足或未构建），转待复核')
    else:
        proj=project_sample(baseline.model,swatch.spectrum);model=baseline.model
        fields=dict(swatch_id=swatch.id,recipe_id=swatch.recipe_id,baseline_id=baseline.id,baseline_version=baseline.version,
            projected_x=proj['x'],projected_y=proj['y'],recon_error=proj['recon_error'],drift_distance=proj['distance'],
            sample_lots=list(baseline.sample_lots))
        if proj['recon_error']>baseline.recon_limit:
            review=DriftReview(**fields,level='pending_review',state='pending_review',
                block_reason=f"重构误差 {proj['recon_error']:.4f} 超过基线 v{baseline.version} 门限 {baseline.recon_limit:.4f}，转待复核")
        else:
            level,z=drift_level(model,proj['distance'])
            note='' if level=='ok' else (f'投影距离偏离基线群落 {z:.2f}σ，轻度漂移' if level=='warn' else f'投影距离偏离基线群落 {z:.2f}σ，显著漂移，建议人工关注')
            review=DriftReview(**fields,level=level,state='projected',block_reason=note)
    db.add(review);log(db,user,f'染样 {swatch.lot} 投影审查 {review.level}');db.commit();return review

def confirm_review(db,key,data,user):
    review=db.scalar(select(DriftReview).where(DriftReview.id==key).with_for_update())
    if not review:raise HTTPException(404,'复核记录不存在')
    if review.state!='pending_review':raise HTTPException(409,'仅待复核记录可裁决，重复裁决被拒绝')
    review.decided_by=user.email;review.decided_at=datetime.utcnow()
    if data.verdict=='normal':
        review.state='confirmed_normal';review.block_reason+='；主管确认正常，复染签批资格保留'
    else:
        review.state='confirmed_anomaly';review.block_reason+='；主管确认异常，冻结该批复染签批资格'
    log(db,user,f'图谱复核 {key} {data.verdict}');db.commit();return review

def swatch_release_guard(db,swatch_id):
    states=db.scalars(select(DriftReview.state).where(DriftReview.swatch_id==swatch_id)).all()
    if 'pending_review' in states:raise HTTPException(409,'染样图谱复核中，待主管确认后才能建立复染试验')
    if 'confirmed_anomaly' in states:raise HTTPException(409,'染样图谱复核确认异常，复染签批资格已冻结')
