from datetime import date
from src.fulfillment_models import DyeLot,DyeIssue,ColorDispatch,ShadeComplaint
from src.drift_models import DriftBaseline,DriftReview
import math,random
from sqlalchemy import select,func
from src.database import Base,engine,Session
from src.models import User,DyeRecipe,Swatch,Trial
from src.production_models import RecipeRevision,DyeBatch
from src.auth import hash_password

def seed():
    Base.metadata.create_all(engine)
    with Session() as db:
        for role in ['admin','colorist','viewer']:
            email=f'{role}@qise.test'
            if not db.scalar(select(User).where(User.email==email)):db.add(User(email=email,password=hash_password('Dye2026!'),role=role))
        recipes=[('DY-021','靛蓝亚麻',1.8,.4,.2),('DY-022','苔绿棉麻',.3,1.7,.7),('DY-023','赤陶平纹',.8,.3,1.5)]
        for code,name,a,b,c in recipes:
            if not db.scalar(select(DyeRecipe).where(DyeRecipe.code==code)):db.add(DyeRecipe(code=code,name=name,dye_a=a,dye_b=b,dye_c=c))
        db.flush();rr=db.scalars(select(DyeRecipe).order_by(DyeRecipe.id)).all();rng=random.Random(42)
        for i in range(60):
            lot=['REF-021','SAMPLE-021','SAMPLE-OFF'][i] if i<3 else f'SW-{i:03}'
            if db.scalar(select(Swatch).where(Swatch.lot==lot)):continue
            group=0 if i<3 else i%3
            l,a,b=(48,-2,-25) if i==0 else (48.7,-1.5,-24.5) if i==1 else (62,8,-14) if i==2 else (48+group*9+rng.uniform(-2,2),-2+group*6+rng.uniform(-1,1),-25+group*15+rng.uniform(-1,1))
            spectrum=[round(min(.95,max(.03,.26+group*.11+.1*math.sin(j/5+group)+rng.gauss(0,.012))),5) for j in range(36)]
            db.add(Swatch(recipe_id=rr[group].id,lot=lot,spectrum=spectrum,l=l,a=a,b=b,measured=True))
        prod=db.scalar(select(DyeRecipe).where(DyeRecipe.code=='DY-PROD'))
        if not prod:
            prod=DyeRecipe(code='DY-PROD',name='量产靛蓝基准',dye_a=1.8,dye_b=.4,dye_c=.2,locked=True);db.add(prod);db.flush()
        for lot,l,a,b in [('PROD-REF',48,-2,-25),('PROD-OK',48.5,-1.8,-24.8)]:
            if not db.scalar(select(Swatch).where(Swatch.lot==lot)):db.add(Swatch(recipe_id=prod.id,lot=lot,spectrum=[.3]*36,l=l,a=a,b=b))
        db.flush();ref=db.scalar(select(Swatch).where(Swatch.lot=='PROD-REF'));candidate=db.scalar(select(Swatch).where(Swatch.lot=='PROD-OK'))
        trial=db.scalar(select(Trial).where(Trial.recipe_id==prod.id,Trial.state=='approved'))
        if not trial:
            trial=Trial(recipe_id=prod.id,reference_swatch_id=ref.id,candidate_swatch_id=candidate.id,delta_e=.574456,state='approved',note='量产演示基准');db.add(trial);db.flush()
        if not db.scalar(select(DyeBatch).where(DyeBatch.code=='DB-DEMO-001')):db.add(DyeBatch(code='DB-DEMO-001',approved_trial_id=trial.id,kg=250,target_snapshot={'lot':ref.lot,'recipe_id':prod.id,'l':ref.l,'a':ref.a,'b':ref.b,'trial_delta_e':trial.delta_e}))
        for code,component,kg,expiry,state in [('DYE-A-1117','A',80,date(2027,12,31),'active'),('DYE-B-1117','B',40,date(2027,12,31),'active'),('DYE-C-1117','C',20,date(2027,12,31),'active'),('DYE-C-HOLD','C',5,date(2027,12,31),'quarantine'),('DYE-B-OLD','B',5,date(2026,1,1),'active')]:
            if not db.scalar(select(DyeLot).where(DyeLot.code==code)):db.add(DyeLot(code=code,component=component,available_kg=kg,expires_on=expiry,state=state))
        mur=db.scalar(select(DyeRecipe).where(DyeRecipe.code=='DY-045'))
        if not mur:
            mur=DyeRecipe(code='DY-045',name='暮山紫斜纹',dye_a=1.2,dye_b=.9,dye_c=.6,locked=True);db.add(mur);db.flush()
        rng2=random.Random(20261120)
        for lot,l,a,b in [('MUR-001',55.0,6.0,-8.0),('MUR-002',55.3,5.8,-8.2),('MUR-003',54.8,6.2,-7.9),('MUR-004',55.2,6.1,-8.1),('MUR-005',54.9,5.9,-8.0),('MUR-006',55.1,6.0,-7.8),('MUR-007',55.4,6.1,-8.2),('MUR-008',55.6,6.4,-7.6)]:
            if db.scalar(select(Swatch).where(Swatch.lot==lot)):continue
            if lot=='MUR-008':spectrum=[round(min(.95,max(.03,.30+.16*math.sin(j/3.2+1.2)+rng2.gauss(0,.008))),5) for j in range(36)]
            else:spectrum=[round(min(.95,max(.03,.34+.09*math.sin(j/4.5)+.04*math.cos(j/7)+rng2.gauss(0,.01))),5) for j in range(36)]
            db.add(Swatch(recipe_id=mur.id,lot=lot,spectrum=spectrum,l=l,a=a,b=b,measured=True))
        db.flush();sw={s.lot:s for s in db.scalars(select(Swatch).where(Swatch.recipe_id==mur.id)).all()}
        for ref_lot,cand_lot in [('MUR-001','MUR-002'),('MUR-003','MUR-004'),('MUR-005','MUR-006')]:
            ref,cand=sw[ref_lot],sw[cand_lot]
            if db.scalar(select(Trial).where(Trial.reference_swatch_id==ref.id,Trial.candidate_swatch_id==cand.id,Trial.state=='approved')):continue
            db.add(Trial(recipe_id=mur.id,reference_swatch_id=ref.id,candidate_swatch_id=cand.id,delta_e=math.dist([ref.l,ref.a,ref.b],[cand.l,cand.a,cand.b]),state='approved',note='暮山紫放行基准'))
        db.flush()
        from src.drift_service import rebuild_baseline,project_swatch
        from src.drift_schemas import BaselineRebuildInput,ProjectInput
        admin=db.scalar(select(User).where(User.email=='admin@qise.test'))
        if not db.scalar(select(DriftBaseline).where(DriftBaseline.recipe_id==mur.id)):rebuild_baseline(db,BaselineRebuildInput(recipe_id=mur.id),admin)
        if not db.scalar(select(DriftReview).where(DriftReview.swatch_id==sw['MUR-008'].id)):project_swatch(db,ProjectInput(swatch_id=sw['MUR-008'].id),admin)
        db.commit()
        print({name:db.scalar(select(func.count()).select_from(model)) for name,model in [('users',User),('recipes',DyeRecipe),('swatches',Swatch)]})
if __name__=='__main__':seed()
