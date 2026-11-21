import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

def calculate_atlas(samples):
    if len(samples)<3:raise ValueError('至少需要三个已测量染样')
    values=np.array([s['spectrum'] for s in samples],dtype=float)
    scaler=StandardScaler();scaled=scaler.fit_transform(values)
    pca=PCA(n_components=2,svd_solver='full',random_state=42)
    projected=pca.fit_transform(scaled)
    reconstructed=pca.inverse_transform(projected)
    return {'explained_variance':pca.explained_variance_ratio_.tolist(),'reconstruction_mse':float(np.mean((scaled-reconstructed)**2)),
            'points':[{'id':s['id'],'lot':s['lot'],'recipe_id':s['recipe_id'],'x':float(v[0]),'y':float(v[1])} for s,v in zip(samples,projected)],
            'count':len(samples),'method':'StandardScaler → PCA / svd_solver=full / random_state=42'}

def _fit(values):
    scaler=StandardScaler();scaled=scaler.fit_transform(values)
    pca=PCA(n_components=2,svd_solver='full',random_state=42)
    projected=pca.fit_transform(scaled)
    return scaler,pca,projected,scaled

def fit_baseline(samples):
    if len(samples)<3:raise ValueError('至少需要三张已放行染样建立基线')
    values=np.array([s['spectrum'] for s in samples],dtype=float)
    scaler,pca,projected,scaled=_fit(values)
    errors=np.mean((scaled-pca.inverse_transform(projected))**2,axis=1)
    center=projected.mean(axis=0);distances=np.linalg.norm(projected-center,axis=1)
    model={'mean':scaler.mean_.tolist(),'scale':scaler.scale_.tolist(),'components':pca.components_.tolist(),
           'center':center.tolist(),'dist_mean':float(distances.mean()),'dist_std':float(distances.std()),
           'points':[{'id':s['id'],'lot':s['lot'],'x':float(v[0]),'y':float(v[1])} for s,v in zip(samples,projected)]}
    # 留一法估计新样本重构误差门限：训练误差对新样本系统性偏紧
    loo=[]
    if len(samples)>=4:
        for i in range(len(samples)):
            s2,p2,_,_=_fit(np.delete(values,i,axis=0))
            x=(values[i]-s2.mean_)/s2.scale_
            loo.append(float(np.mean((x-(x@p2.components_.T)@p2.components_)**2)))
    basis=loo if loo else errors.tolist()
    limit=max(float(np.mean(basis)+3*np.std(basis)),float(max(basis))*1.2)
    return {'model':model,'explained_variance':pca.explained_variance_ratio_.tolist(),
            'recon_limit':limit,'train_mse':float(errors.mean()),'loo_mse':float(np.mean(basis)),
            'method':'StandardScaler → PCA / svd_solver=full / random_state=42 / 留一法门限'}

def project_sample(model,spectrum):
    scaled=(np.array(spectrum,dtype=float)-np.array(model['mean']))/np.array(model['scale'])
    components=np.array(model['components']);point=scaled@components.T
    error=float(np.mean((scaled-point@components)**2))
    return {'x':float(point[0]),'y':float(point[1]),'recon_error':error,
            'distance':float(np.linalg.norm(point-np.array(model['center'])))}

def drift_level(model,distance):
    std=model['dist_std'];z=0.0 if std<1e-9 else (distance-model['dist_mean'])/std
    if z<=2:return 'ok',float(z)
    if z<=3:return 'warn',float(z)
    return 'drift',float(z)
