#!/usr/bin/env python
# coding: utf-8

# In[ ]:


get_ipython().run_line_magic('matplotlib', 'inline')
from pylab import *


# In[ ]:


from deficit_defs import *


# ## From a deficit, compare the rates of 
# 
# - fix (just lenses)
# - patch
# - blur
# - contrast
# - constrast + mask
# 
# Fixed params
# 
# - open eye noise =0.1
# - time of 100 hours (arbitrary)
# 
# Measure
# 
# - response (max response to gratings, across spatial freq and orientiation)
# - recovery rate per hour

# In[ ]:


def run_one_continuous_fix(params,overwrite=False):
    import plasticnet as pn
    count,eta,noise,number_of_neurons,sfname=(params.count,params.eta,params.noise,
                                        params.number_of_neurons,params.sfname)
    
    if not overwrite and os.path.exists(sfname):
        return sfname
    
    seq=pn.Sequence()
    # deliberately use a standard deficit, with it's own eta and noise
    seq+=deficit(number_of_neurons=params.number_of_neurons,total_time=1*day,) 

    seq+=fix(total_time=10*hour, # total_time=100*hour,
             save_interval=20*minute,number_of_neurons=params.number_of_neurons,
             eta=eta,noise=noise)

    seq.run(display_hash=False)
    pn.save(sfname,seq) 
    
    return sfname
    


# use $\eta=1e-6$ for everything to make the comparison clear

# In[ ]:


def run_one_continuous_blur(params,overwrite=False):
    import plasticnet as pn
    count,blur,eta,noise,number_of_neurons,sfname=(params.count,params.blur,params.eta,params.noise,
                                        params.number_of_neurons,params.sfname)
    
    if not overwrite and os.path.exists(sfname):
        return sfname
    
    
    seq=pn.Sequence()
    # deliberately use a standard deficit, with it's own eta and noise
    seq+=deficit(number_of_neurons=params.number_of_neurons) 

    seq+=treatment(blur=blur,
                   noise=0.1,
                   noise2=noise,  # treated (strong-eye) noise
                   total_time=100*hour,number_of_neurons=params.number_of_neurons,
                   eta=eta,
                   save_interval=20*minute)
    

    seq.run(display_hash=False)
    pn.save(sfname,seq) 
    
    return sfname
    
    
def run_one_continuous_patch(params,overwrite=False):
    import plasticnet as pn
    count,eta,noise,number_of_neurons,sfname=(params.count,params.eta,params.noise,
                                        params.number_of_neurons,params.sfname)
    
    if not overwrite and os.path.exists(sfname):
        return sfname
    
    
    seq=pn.Sequence()
    # deliberately use a standard deficit, with it's own eta and noise
    seq+=deficit(number_of_neurons=params.number_of_neurons) 
    
    seq+=patch_treatment(patch_noise=noise,
               total_time=100*hour,number_of_neurons=params.number_of_neurons,
               eta=eta,
               save_interval=20*minute)

    seq.run(display_hash=False,print_time=True)
    pn.save(sfname,seq) 
    
    return sfname
        


# In[ ]:


def run_one_continuous_mask(params,overwrite=False):
    import plasticnet as pn
    count,eta,contrast,mask,f,number_of_neurons,sfname=(params.count,params.eta,params.contrast,params.mask,params.f,
                                        params.number_of_neurons,params.sfname)
    
    if not overwrite and os.path.exists(sfname):
        return sfname

    
    seq=pn.Sequence()
    # deliberately use a standard deficit, with it's own eta and noise
    seq+=deficit(number_of_neurons=params.number_of_neurons) 

    seq+=treatment(f=f,
                   mask=mask,
                   contrast=contrast,
                   total_time=100*hour,
                   eta=eta,
                   save_interval=20*minute)

    seq.run(display_hash=False,print_time=True)
    pn.save(sfname,seq) 

    
    return sfname
    
    


# ## This for all sims

# In[ ]:


def to_named_tuple(params_list):
    from collections import namedtuple
    keys=list(params_list[0].keys())
    keys+=['count']
    params=namedtuple('params',keys)
    
    tuples_list=[]
    for count,p in enumerate(params_list):
        p2=params(count=count,
                  **p)
        tuples_list.append(p2)
        
        
    return tuples_list


# In[ ]:


def make_do_params(all_params,verbose=False):
    do_params=[]
    for p in all_params:
        if os.path.exists(p.sfname):
            print("Skipping %s...already exists" % p.sfname)
        else:
            do_params+=[p]

    if verbose:
        print("%d sims" % len(do_params))    
        if len(do_params)<=15:
            print(do_params)
        else:
            print(do_params[:5],"...",do_params[-5:])        
    return do_params


# In[ ]:


number_of_neurons=20
eta=1e-6
number_of_processes=4


# ## Continuous Fix

# In[ ]:


func=run_one_continuous_fix

noise_mat=linspace(0,1,11)

all_params=[]
for n,noise in enumerate(noise_mat):
    sfname=f'sims-2021-11-19/continuous fix {number_of_neurons} neurons noise {noise:.1f}.asdf'
    
    p=Struct()
    p.eta=eta
    p.number_of_neurons=number_of_neurons
    p.sfname=sfname
    
    p.noise=noise
    
    all_params+=[p]

all_params=to_named_tuple(all_params)  


# In[ ]:


get_ipython().run_cell_magic('time', '', 'print(func.__name__)\nfunc(all_params[0],overwrite=True)\n')


# In[ ]:


do_params=make_do_params(all_params,verbose=True)


# In[ ]:


real_time=2*minute+ 38
print(time2str(real_time*len(do_params)/number_of_processes))


# In[ ]:


set_start_method('fork',force=True)
with Pool(processes=number_of_processes) as pool:
    result = pool.map_async(func, do_params,chunksize=number_of_processes)
    print(result.get())


# ## Patch

# In[ ]:


func=func=run_one_continuous_patch

closed_eye_noise_mat=linspace(0,1,21)

all_params=[]
for n,noise in enumerate(closed_eye_noise_mat):
    sfname=f'sims-2021-11-19/continuous patch {number_of_neurons} neurons noise {noise:.1f}.asdf'
    
    p=Struct()
    p.eta=eta
    p.number_of_neurons=number_of_neurons
    p.sfname=sfname
    
    p.noise=noise
    
    all_params+=[p]

all_params=to_named_tuple(all_params)  


# In[ ]:


# %%time
# print(func.__name__)
# func(all_params[0],overwrite=True)


# In[ ]:


do_params=make_do_params(all_params,verbose=True)


# In[ ]:


real_time=8*minute+ 46
print(time2str(real_time*len(do_params)/number_of_processes))


# In[ ]:


pool = Pool(processes=number_of_processes)
result = pool.map_async(func, do_params)
print(result.get())


# ## Atropine

# In[ ]:


func=func=run_one_continuous_blur


atropine_blur_mat=linspace(0,6,21)
closed_eye_noise_mat=linspace(0,1,11)

all_params=[]
for b,blur in enumerate(atropine_blur_mat):
    for n,noise in enumerate(closed_eye_noise_mat):
        sfname=f'sims-2021-11-19/continuous atropine {number_of_neurons} neurons noise {noise:.1f} blur {blur:0.1f}.asdf'

        p=Struct()
        p.eta=eta
        p.number_of_neurons=number_of_neurons
        p.sfname=sfname

        p.noise=noise
        p.blur=blur

        all_params+=[p]

all_params=to_named_tuple(all_params)  


# In[ ]:


# %%time
# print(func.__name__)
# func(all_params[0],overwrite=True)


# In[ ]:


do_params=make_do_params(all_params,verbose=True)


# In[ ]:


real_time=7*minute+ 37
print(time2str(real_time*len(do_params)/number_of_processes))


# In[ ]:


pool = Pool(processes=number_of_processes)
result = pool.map_async(func, do_params)
print(result.get())


# ## Contrast

# In[ ]:


func=func=run_one_continuous_mask


contrast_mat=linspace(0,1,11)
mask_mat=array([0,1])
f_mat=array([10,30,50,70,90])


all_params=[]
for c,contrast in enumerate(contrast_mat):
    sfname=f'sims-2021-11-19/continuous contrast {number_of_neurons} neurons contrast {contrast:.1f}.asdf'

    p=Struct()
    p.eta=eta
    p.number_of_neurons=number_of_neurons
    p.sfname=sfname

    p.contrast=contrast
    p.mask=0
    p.f=10. # not used when mask=0

    all_params+=[p]

all_params=to_named_tuple(all_params)  


# In[ ]:


do_params=make_do_params(all_params,verbose=True)


# In[ ]:


# %%time
# print(func.__name__)
# func(all_params[0],overwrite=True)


# In[ ]:





# In[ ]:


real_time=7*minute+ 55
print(time2str(real_time*len(do_params)/number_of_processes))


# In[ ]:


pool = Pool(processes=number_of_processes)
result = pool.map_async(func, do_params)
print(result.get())


# ## Contrast with Mask

# In[ ]:


func=func=run_one_continuous_mask


contrast_mat=linspace(0,1,11)
mask_mat=array([0,1])
f_mat=array([10,30,50,70,90])


all_params=[]
for c,contrast in enumerate(contrast_mat):
    for fi,f in enumerate(f_mat):
        sfname=f'sims-2021-11-19/continuous contrast {number_of_neurons} neurons contrast {contrast:.1f} mask f {f}.asdf'

        p=Struct()
        p.eta=eta
        p.number_of_neurons=number_of_neurons
        p.sfname=sfname

        p.contrast=contrast
        p.mask=1
        p.f=f # not used when mask=0

        all_params+=[p]

all_params=to_named_tuple(all_params)  


# In[ ]:


# %%time
# print(func.__name__)
# func(all_params[0],overwrite=True)


# In[ ]:


do_params=make_do_params(all_params,verbose=True)


# In[ ]:


real_time=8*minute+ 8
print(time2str(real_time*len(do_params)/number_of_processes))


# In[ ]:


pool = Pool(processes=number_of_processes)
result = pool.map_async(func, do_params)
print(result.get())

