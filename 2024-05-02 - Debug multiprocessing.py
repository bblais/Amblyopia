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


import ray 

@ray.remote
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


# %%time
# print(func.__name__)
# func(all_params[0],overwrite=True)


# In[ ]:


do_params=make_do_params(all_params,verbose=True)


# In[ ]:


real_time=2*minute+ 38
print(time2str(real_time*len(do_params)/number_of_processes))


# In[ ]:


# 2 minutes each for a 20 second simulation
# set_start_method('fork',force=True)
# with Pool(processes=number_of_processes) as pool:
#     result = pool.map_async(func, do_params)
#     print(result.get())


# In[ ]:


#import ipyparallel as ipp


# In[ ]:


# gets pickling error
# with ipp.Cluster(n=4) as rc:
#     view = rc.load_balanced_view()
#     asyncresult = view.map_async(func, do_params)
#     asyncresult.wait_interactive()
#     result = asyncresult.get()


# In[ ]:


ray.init(num_cpus=4)


# In[ ]:


results = [func.remote(p) for p in do_params]
sfnames=ray.get(results)


# In[ ]:


sfnames


# In[ ]:




