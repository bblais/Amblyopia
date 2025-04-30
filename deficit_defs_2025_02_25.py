#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import plasticnet as pn
from splikes.utils import paramtext
import process_images_hdf5 as pi5
import os
from savevars import savevars,loadvars
from tqdm.notebook import tqdm

import platform
_debug = 'Darwin' in platform.platform()

_debug=False
if _debug:
    print("\n****Debugging****\n")


print(platform.platform())

from numpy import linspace,array,meshgrid
import ray


from collections import namedtuple


second=1
ms=0.001*second
minute=60*second
hour=60*minute
day=24*hour

from plotutils import *


import process_images_hdf5 as pi5
import os

def time2str(tm):

    frac=tm-int(tm)
    tm=int(tm)

    s=''
    sc=tm % 60
    tm=tm//60

    mn=tm % 60
    tm=tm//60

    hr=tm % 24
    tm=tm//24
    dy=tm

    if (dy>0):
        s=s+"%d d, " % dy

    if (hr>0):
        s=s+"%d h, " % hr

    if (mn>0):
        s=s+"%d m, " % mn


    s=s+"%.2f s" % (sc+frac)

    return s


from mpl_toolkits.axes_grid1 import make_axes_locatable
import matplotlib as mpl
def truncate_colormap(cmap, minval=0.0, maxval=1.0, n=100):
    import matplotlib as mpl
    new_cmap = mpl.colors.LinearSegmentedColormap.from_list(
        'trunc({n},{a:.2f},{b:.2f})'.format(n=cmap.name, a=minval, b=maxval),
        cmap(np.linspace(minval, maxval, n)))
    return new_cmap
Blues2 = truncate_colormap(mpl.cm.Blues, 0.3, 1.0)
Oranges2 = truncate_colormap(mpl.cm.Oranges, 0.3, 1.0)
Blues2r = truncate_colormap(mpl.cm.Blues, 0.3, 1.0).reversed()
Oranges2r = truncate_colormap(mpl.cm.Oranges, 0.3, 1.0).reversed()


class Storage(object):
    def __init__(self):
        self.data=[]

    def __add__(self,other):
        s=Storage()
        s+=other
        return s

    def __iadd__(self,other):
        self.append(*other)
        return self

    def append(self,*args):
        if not self.data:
            for arg in args:
                self.data.append([arg])

        else:
            for d,a in zip(self.data,args):
                d.append(a)

    def arrays(self):
        for i in range(len(self.data)):
            self.data[i]=array(self.data[i])

        ret=tuple(self.data)
        if len(ret)==1:
            return ret[0]
        else:
            return ret

    def __array__(self):
        from numpy import vstack
        return vstack(self.arrays())




def default_post(number_of_neurons):
    post=pn.neurons.linear_neuron(number_of_neurons)
    post+=pn.neurons.process.sigmoid(0,50)
    return post

def default_bcm(pre,post,orthogonalization=True):
    c=pn.connections.BCM(pre,post,[-.01,.01],[.1,.2])

    if orthogonalization:
        c+=pn.connections.process.orthogonalization(10*minute)

    c.eta=2e-6
    c.tau=15*pn.minute   

    return c


from asdf.extension import Converter


class ResultsConverter(Converter):
    tags = ["asdf://example.com/deficit_defs/tags/results-1.0.0"]
    types = ["deficit_defs.Results"]
    varnames=['fname','all_responses','k_mat','theta_mat',
                    'sequence_index','sequence_times','sequence_weights',
                    't','y','θ','num_neurons','num_channels','rf_size']

    def to_yaml_tree(self, obj, tag, ctx):
        D={}

        for name in self.varnames:
            D[name]=obj.__getattribute__(name)

        return D


    def from_yaml_tree(self, node, tag, ctx):
        import time
        D={}

        for name in self.varnames:
            D[name]=node[name]


        D['fname']=str(D['fname'])
        names=['num_neurons','num_channels','rf_size']
        for name in names:
            D['name']=int(D[name])

        names=['sequence_index','sequence_times',]
        for name in names:
            D['name']=list(D[name])

        name='sequence_weights'
        D[name]=[(np.array(_[0]),np.array(_[1])) for _ in D[name]]


        name='all_responses'
        D[name]=[(np.array(_[0]),np.array(_[1])) for _ in D[name]]


        names=['k_mat','theta_mat',
                    't','y','θ']
        for name in names:
            D['name']=np.array(D[name])

        return Results(D)

import asdf
from asdf.extension import Extension


class ResultsExtension(Extension):
    extension_uri = "asdf://example.com/deficit_defs/extensions/results-1.0.0"
    converters = [ResultsConverter()]
    tags = ["asdf://example.com/deficit_defs/tags/results-1.0.0"]


asdf.get_config().add_extension(ResultsExtension())


class Results(object):

    def __init__(self,sfname):
        if isinstance(sfname,dict):
            D=sfname
            for key in D:
                self.__setattr__(key,D[key])

        else:
            self.fname=sfname

            t_mat,y_mat=self.get_max_responses()
            self.all_responses,self.k_mat,self.theta_mat=get_responses(self.fname)


            self.sequence_index=[]
            self.sequence_times=[]
            count=0
            for t in t_mat:
                self.sequence_times.append((t.min(),t.max()))
                self.sequence_index.append((count,count+len(t)-1))
                count+=len(t)

            self.t=np.concatenate(t_mat)
            self.y=np.concatenate(y_mat)

            _,self.num_neurons,self.num_channels=self.y.shape


            t2_mat,θ_mat=self.get_theta()
            assert sum(t2_mat[0]-t_mat[0])==0.0

            self.θ=np.concatenate(θ_mat)

            t2_mat,W_mat=self.get_weights()
            assert sum(t2_mat[0]-t_mat[0])==0.0
            self._W=np.concatenate(W_mat)


            self.sequence_weights=[]
            for idx1,idx2 in self.sequence_index:
                self.sequence_weights.append( (self.W[idx1,:,:],self.W[idx2,:,:]) )


            self.rf_size=int(np.sqrt(self.W.shape[-1]/self.num_channels))


    @property
    def W(self):
        if self._W is None:
            t2_mat,W_mat=self.get_weights()
            self._W=np.concatenate(W_mat)

        return self._W




    def __getitem__(self,idx):
        if idx==-1:  # make time the 0th index
            return [np.stack([_]) for _ in (self.t[-1],self.y[-1,...],self.θ[-1,...],self.W[-1,...])]

        try:

            ts=[]
            ys=[]
            θs=[]
            Ws=[]
            for _t in idx:
                t,y,θ,W=self[_t]
                ts.append(t)
                ys.append(y)
                θs.append(θ)
                Ws.append(W)


            t=np.concatenate(ts)
            y=np.concatenate(ys)
            θ=np.concatenate(θs)
            W=np.concatenate(Ws)

            return t,y,θ,W

        except TypeError:  # a single number, # make time the 0th index
            _t=idx
            idx=np.where(self.t>=_t)[0][0]

            return [np.stack([_]) for _ in (self.t[idx],self.y[idx,...],self.θ[idx,...],self.W[idx,...])]

    def μσ_at_t(self,t):
        _t,y,θ,W=self[t]
        μ=y.mean(axis=1)  # average across neurons, at the end of a seq, for each channel
        S=y.std(axis=1)
        N=y.shape[1]
        K=1+20/N**2
        σ=K*S/np.sqrt(N)

        return μ,σ



    @property
    def ORI(self):
        from numpy import radians,cos,sin,sqrt,hstack,concatenate
        tt=[]
        LL=[]
        for response in self.all_responses:

            t,y=response
            tt.append(t)

            y=y.max(axis=0)
            θk=radians(self.theta_mat)

            rk=y.transpose([1,2,3,0])  # make the angle the right-most index, so broadcaasting works

            vx=rk*cos(2*θk)
            vy=rk*sin(2*θk)

            L=sqrt(vx.sum(axis=3)**2+vy.sum(axis=3)**2)/rk.sum(axis=3)
            L=L.transpose([0,2,1])
            LL.append(L)

        t=hstack(tt)
        ORI=concatenate(LL,axis=1)
        return ORI

    @property
    def max_SF(self):
        from numpy import hstack,concatenate,repeat,expand_dims,newaxis,log,argmax

        tt=[]
        LL=[]
        for response in self.all_responses:
            t,y=response    # k, theta, channel, neuron, time
            y=y.max(axis=1)  # optimize over theta
            rk=y.transpose([1,2,3,0])
            L=self.k_mat[argmax(rk,axis=3)]

            tt.append(t)
            L=L.transpose([2,1,0])  # want it to be time, neurons, channel
            LL.append(L)

        t=hstack(tt)
        kk=concatenate(LL,axis=0)

        return kk

    @property
    def SF_Var(self):
        from numpy import hstack,concatenate,repeat,expand_dims,newaxis,log,argmax
        tt=[]
        LL=[]
        for response in self.all_responses:
            t,y=response    # k, theta, channel, neuron, time
            y=y.max(axis=1)  # optimize over theta
            rk=y.transpose([1,2,3,0])
            norm_rk=rk.sum(axis=3)
            norm_rk=expand_dims(norm_rk,3)
            kopt=repeat(self.k_mat[argmax(rk,axis=3)][:, :, :,newaxis],len(self.k_mat),axis=3)
            L=(rk*(log(self.k_mat)-log(kopt))**2/norm_rk).sum(axis=3)

            tt.append(t)
            L=L.transpose([2,1,0])  # want it to be time, neurons, channel
            LL.append(L)

        t=hstack(tt)
        kk=concatenate(LL,axis=0)        
        return kk

    @property
    def ODI(self):
        return (self.y[:,:,1]-self.y[:,:,0])/(self.y[:,:,1]+self.y[:,:,0]) 




    @property
    def ODI_μσ(self):
        μ_mat=[]
        σ_mat=[]
        for index in self.sequence_index:
            idx=index[-1]

            μ=self.ODI[idx,...].mean(axis=0)  # average across neurons, at the end of a seq, for each channel
            S=self.ODI[idx,...].std(axis=0)
            N=self.y.shape[1]
            K=1+20/N**2
            σ=K*S/np.sqrt(N)

            μ_mat.append(μ)
            σ_mat.append(σ)

        return μ_mat,σ_mat


    def plot_rf_grid(self,which_neurons=None):
        from pylab import GridSpec,subplot,imshow,ylabel,title,gca,xlabel,grid,cm,figure,axis

        w_im=self.weight_image(self.W[-1,::])
        number_of_neurons=w_im.shape[0]

        if which_neurons is None:
            which_neurons=list(range(number_of_neurons))

        N=len(which_neurons)

        num_channels=2

        nr=int(np.ceil(np.sqrt(N)))
        nc=int(np.ceil(N/nr))


        fig1=figure(figsize=(12,12))
        ni=0
        for i in range(number_of_neurons):

            if i not in which_neurons:
                continue

            vmin=w_im[i,:,:,:].min()
            vmax=w_im[i,:,:,:].max()
            for c in range(num_channels):

                subplot(nr,nc*num_channels,num_channels*ni+c+1)
                axis('equal')
                im=w_im[i,c,:,:]
                imshow(im,cmap=cm.gray,vmin=vmin,vmax=vmax,interpolation='nearest')
                grid(False)
                if c==0:
                    ylabel(f'Neuron {i}')
                if ni==0:
                    if c==0:
                        title("Left")
                    else:
                        title("Right")
                gca().set_xticklabels([])
                gca().set_yticklabels([])                


            ni+=1



    def plot_rf(self):
        from pylab import GridSpec,subplot,imshow,ylabel,title,gca,xlabel,grid,cm


        w_im=self.weight_image(self.W[-1,::])
        number_of_neurons=w_im.shape[0]

        spec2 = GridSpec(ncols=w_im.shape[1], nrows=w_im.shape[0])
        for n in range(number_of_neurons):
            vmin=w_im[n,:,:,:].min()
            vmax=w_im[n,:,:,:].max()
            for c in range(2):
                subplot(spec2[n, c])
                im=w_im[n,c,:,:]
                imshow(im,cmap=cm.gray,vmin=vmin,vmax=vmax,interpolation='nearest')
                grid(False)
                if c==0:
                    ylabel(f'Neuron {n}')
                if n==0:
                    if c==0:
                        title("Left")
                    else:
                        title("Right")
                gca().set_xticklabels([])
                gca().set_yticklabels([])

    @property
    def μσ(self):

        μ_mat=[]
        σ_mat=[]
        for index in self.sequence_index:
            idx=index[-1]

            μ=self.y[idx,...].mean(axis=0)  # average across neurons, at the end of a seq, for each channel
            S=self.y[idx,...].std(axis=0)
            N=self.y.shape[1]
            K=1+20/N**2
            σ=K*S/np.sqrt(N)

            μ_mat.append(μ)
            σ_mat.append(σ)

        return μ_mat,σ_mat

    def weight_image(self,W):
        return W.reshape((self.num_neurons,self.num_channels,self.rf_size,self.rf_size))

    def get_max_responses(self):

        fname=self.fname

        t_mat=[]
        y_mat=[]
        with asdf.open(fname) as af:
            L=af.tree['attrs']['sequence length']

            for i in range(L):
                m=af.tree['sequence %d' % i]['simulation']['process 0']
                t,responses=m['t'],m['responses']
                t_mat.append(np.array(t))
                y=pn.utils.max_channel_response(np.array(responses))
                y=y.transpose([2,1,0])  # make time the index 0, neurons index 1, and channels index 2
                y_mat.append(y)

        return t_mat,y_mat

    def get_theta(self):
        fname=self.fname

        t_mat=[]
        theta_mat=[]
        with asdf.open(fname) as af:
            L=af.tree['attrs']['sequence length']

            for i in range(L):
                m=af.tree['sequence %d' % i]['connection 0']['monitor theta']           
                t,theta=m['t'],m['values']
                t_mat.append(np.array(t))
                theta_mat.append(np.array(theta))

        return t_mat,theta_mat


    def get_weights(self):
        fname=self.fname

        t_mat=[]
        W_mat=[]
        with asdf.open(fname) as af:
            L=af.tree['attrs']['sequence length']

            for i in range(L):
                m=af.tree['sequence %d' % i]['connection 0']['monitor weights']
                t,W=m['t'],m['values']
                t_mat.append(np.array(t))
                W_mat.append(np.array(W))

        return t_mat,W_mat


def μσ(V,axis=None):
    μ=v.mean(axis=axis)
    S=v.std(axis=axis)
    if axis is None:
        N=len(v.ravel())
    else:
        N=V.shape[axis]

    K=1+20/N**2
    σ=K*S/sqrt(N)    

    return μ,σ

global base_image_file
base_image_file='asdf/bbsk081604_all_scale2.asdf'
print("Base Image File:",base_image_file)

def deficit(blur=2.5,noise=0.1,rf_size=19,eta=2e-6,
           number_of_neurons=10,
           total_time=8*day,
           save_interval=1*hour):


    if _debug:
        total_time=1*minute
        save_interval=1*second


    if blur<0:
        blur_fname=Lnorm_fname=pi5.filtered_images(base_image_file)
    else:
        blur_fname=pi5.filtered_images(base_image_file,
                                    {'type':'blur','size':blur},
                                    )

    Rnorm_fname=pi5.filtered_images(base_image_file,
                                  )

    pre1=pn.neurons.natural_images(blur_fname,
                                   rf_size=rf_size,verbose=False)

    pre2=pn.neurons.natural_images(Rnorm_fname,rf_size=rf_size,
                                other_channel=pre1,
                                verbose=False)

    sigma=noise
    pre1+=pn.neurons.process.add_noise_normal(0,sigma)

    sigma=noise
    pre2+=pn.neurons.process.add_noise_normal(0,sigma)

    pre=pre1+pre2

    post=default_post(number_of_neurons)
    c=default_bcm(pre,post)
    c.eta=eta

    sim=pn.simulation(total_time)
    sim.dt=200*ms

    sim.monitor(post,['output'],save_interval)
    sim.monitor(c,['weights','theta'],save_interval)

    sim+=pn.grating_response(print_time=False)

    return sim,[pre,post],[c]


def fix(noise=0.1,rf_size=19,
           number_of_neurons=10,
           total_time=8*day,
           save_interval=1*hour,
           eta=2e-6):

    if _debug:
        total_time=1*minute
        save_interval=1*second



    Lnorm_fname=pi5.filtered_images(base_image_file)
    Rnorm_fname=pi5.filtered_images(base_image_file)

    pre1=pn.neurons.natural_images(Lnorm_fname,rf_size=rf_size,
                                verbose=False)
    pre2=pn.neurons.natural_images(Rnorm_fname,rf_size=rf_size,
                                other_channel=pre1,
                                verbose=False)


    sigma=noise
    pre1+=pn.neurons.process.add_noise_normal(0,sigma)

    sigma=noise
    pre2+=pn.neurons.process.add_noise_normal(0,sigma)

    pre=pre1+pre2

    post=default_post(number_of_neurons)
    c=default_bcm(pre,post)
    c.eta=eta

    save_interval=save_interval

    sim=pn.simulation(total_time)

    sim.dt=200*ms

    sim.monitor(post,['output'],save_interval)
    sim.monitor(c,['weights','theta'],save_interval)

    sim+=pn.grating_response(print_time=False)

    return sim,[pre,post],[c]


def treatment(contrast=1,noise=0.1,noise2=0.1,
              rf_size=19,eta=5e-6,
              f=30,  # size of the blur for mask, which is a measure of overlap
           number_of_neurons=20,
           total_time=8*day,
           save_interval=1*hour,
             mask=None,
             blur=0,
              apply_mask_to_average=False):

    if _debug:
        total_time=1*minute
        save_interval=1*second


    if not f in [10,30,50,70,90]:
        raise ValueError("Unknown f %s" % str(f))


    if mask:
        if blur:
            maskA_fname=pi5.filtered_images(base_image_file,
                                        {'type':'blur','size':blur},
                                        {'type':'mask',
                                         'name':'bblais-masks-20210615/2021-06-15-*-A-fsig%d.png'% f, 
                                        'seed':101,
                                        'apply_to_average':apply_mask_to_average,
                                        },
                                            verbose=False,
                                      )
            maskF_fname=pi5.filtered_images(base_image_file,
                                        {'type':'blur','size':blur},
                                        {'type':'mask',
                                         'name':'bblais-masks-20210615/2021-06-15-*-F-fsig%d.png' % f, 
                                        'seed':101,
                                        'apply_to_average':apply_mask_to_average,
                                        },
                                            verbose=False,
                                      )            
        else:
            maskA_fname=pi5.filtered_images(base_image_file,
                                        {'type':'mask',
                                         'name':'bblais-masks-20210615/2021-06-15-*-A-fsig%d.png' % f,
                                        'seed':101,
                                        'apply_to_average':apply_mask_to_average,
                                        },
                                            verbose=False,
                                      )
            maskF_fname=pi5.filtered_images(base_image_file,
                                        {'type':'mask',
                                         'name':'bblais-masks-20210615/2021-06-15-*-F-fsig%d.png' % f,
                                        'seed':101,
                                        'apply_to_average':apply_mask_to_average,
                                        },
                                            verbose=False,
                                      )

        pre1=pn.neurons.natural_images(maskA_fname,rf_size=rf_size,
                                    verbose=False)
        pre2=pn.neurons.natural_images(maskF_fname,rf_size=rf_size,
                                    other_channel=pre1,
                                    verbose=False)

    else:

        if blur:
            blur_fname=pi5.filtered_images(base_image_file,
                                        {'type':'blur','size':blur},
                                            verbose=False,
                                          )

        norm_fname=pi5.filtered_images(base_image_file,
                                            verbose=False,
                                      )


        pre1=pn.neurons.natural_images(norm_fname,rf_size=rf_size,
                                    verbose=False)

        if blur:
            pre2=pn.neurons.natural_images(blur_fname,rf_size=rf_size,
                                        other_channel=pre1,
                                        verbose=False)
        else:
            pre2=pn.neurons.natural_images(norm_fname,rf_size=rf_size,
                                        other_channel=pre1,
                                        verbose=False)



    sigma=noise
    pre1+=pn.neurons.process.add_noise_normal(0,sigma)

    sigma=noise2
    pre2+=pn.neurons.process.scale_shift(contrast,0)
    pre2+=pn.neurons.process.add_noise_normal(0,sigma)

    pre=pre1+pre2

    post=pn.neurons.linear_neuron(number_of_neurons)
    post+=pn.neurons.process.sigmoid(-1,50)

    c=pn.connections.BCM(pre,post,[-.1,.1],[.1,.2])
    c.eta=eta
    c.tau=100*second

    save_interval=save_interval

    sim=pn.simulation(total_time)

    sim.dt=200*ms

    sim.monitor(post,['output'],save_interval)
    sim.monitor(c,['weights','theta'],save_interval)

    sim+=pn.grating_response(print_time=False)

    return sim,[pre,post],[c]

def patch_treatment(noise=0.1,patch_noise=0.1,rf_size=19,
                   number_of_neurons=20,
                   total_time=8*day,
                   save_interval=1*hour,
                   eta=2e-6,
                   ):

    if _debug:
        total_time=1*minute
        save_interval=1*second

    norm_fname=pi5.filtered_images(base_image_file,
                                verbose=False
                                  )


    pre1=pn.neurons.natural_images(norm_fname,rf_size=rf_size,
                                verbose=False)

    pre2=pn.neurons.natural_images(norm_fname,rf_size=rf_size,
                                other_channel=pre1,
                                verbose=False)



    sigma=noise
    pre1+=pn.neurons.process.add_noise_normal(0,sigma)

    sigma=patch_noise
    pre2+=pn.neurons.process.scale_shift(0.0,0) # zero out signal
    pre2+=pn.neurons.process.add_noise_normal(0,sigma)

    pre=pre1+pre2

    post=default_post(number_of_neurons)
    c=default_bcm(pre,post)
    c.eta=eta

    save_interval=save_interval

    sim=pn.simulation(total_time)

    sim.dt=200*ms

    sim.monitor(post,['output'],save_interval)
    sim.monitor(c,['weights','theta'],save_interval)

    sim+=pn.grating_response(print_time=False)

    return sim,[pre,post],[c]


def get_responses(fname):
    import asdf
    import numpy as np

    data=[]
    with asdf.open(fname) as af:
        L=af.tree['attrs']['sequence length']

        for i in range(L):
            m=af.tree['sequence %d' % i]['simulation']['process 0']
            t,responses=m['t'],m['responses']
            data.append( (np.array(t),np.array(responses)) )

        k_mat=np.array(m['k_mat'])
        theta_mat=np.array(m['theta_mat'])

    return data,k_mat,theta_mat        


# In[ ]:


def get_max_responses(all_params):
    import plasticnet as pn
    import numpy as np

    # after deficit
    μ=[]
    σ=[]

    max_responses={}

    for i,params in enumerate(all_params):

        count,number_of_neurons,sfname=(params.count,
                                        params.number_of_neurons,
                                        params.sfname)

        if not count in max_responses:
            max_responses[count]=[]

        y=max_responses[count]

        all_responses,k_mat,theta_mat=get_responses(sfname)
        t,responses=all_responses[0]   #<===== first sim in sequence (aka deficit)

        num_channels,num_neurons=responses.shape[2],responses.shape[3]

        y.append(responses[:,:,:,:,-1].max(axis=0).max(axis=0))


    for count in max_responses:
        y=max_responses[count]=np.hstack(max_responses[count])

        μ.append(y.mean(axis=1))
        S=y.std(axis=1)
        N=np.sqrt(y.shape[1])
        K=1+20/N**2
        σ.append(K*S/np.sqrt(N))

    μ1=np.array(μ).T
    σ1=np.array(σ).T

    #======= end 
    μ=[]
    σ=[]

    max_responses={}

    for i,params in enumerate(all_params):

        count,number_of_neurons,sfname=(params.count,
                                        params.number_of_neurons,
                                        params.sfname)

        if not count in max_responses:
            max_responses[count]=[]

        y=max_responses[count]

        all_responses,k_mat,theta_mat=get_responses(sfname)
        t,responses=all_responses[-1]  #<===== last sim in sequence

        num_channels,num_neurons=responses.shape[2],responses.shape[3]

        y.append(responses[:,:,:,:,-1].max(axis=0).max(axis=0))


    for count in max_responses:
        y=max_responses[count]=np.hstack(max_responses[count])

        μ.append(y.mean(axis=1))
        S=y.std(axis=1)
        N=np.sqrt(y.shape[1])
        K=1+20/N**2
        σ.append(K*S/np.sqrt(N))

    μ2=np.array(μ).T
    σ2=np.array(σ).T




    return μ1,σ1,μ2,σ2

def get_last_max_responses(all_params):
    import plasticnet as pn
    import numpy as np


    from tqdm import tqdm

    max_responses={}

    for i,params in tqdm(enumerate(all_params), total=len(all_params)):

        count,number_of_neurons,sfname=(params.count,
                                        params.number_of_neurons,
                                        params.sfname)

        if not count in max_responses:
            max_responses[count]=[]

        y=max_responses[count]

        all_responses,k_mat,theta_mat=get_responses(sfname)

        for t,responses in all_responses:
            num_channels,num_neurons=responses.shape[2],responses.shape[3]

            # this is the response, maxed over k and theta, at the end of this part of the sequence
            y.append(responses[:,:,:,:,-1].max(axis=0).max(axis=0))

    # parameter count, sequence count, channel count, neuron count
    return array([max_responses[_] for _ in range(len(max_responses))])


def μσ(y,axis=None):
    from numpy import prod,sqrt

    μ=y.mean(axis=axis)
    S=y.std(axis=axis)

    N_max=prod(y.shape)
    try:
        N_min=prod(μ.shape)
    except AttributeError:
        N_min=1

    N=N_max/N_min
    K=1+20/N**2
    σ=K*S/sqrt(N)

    return μ,σ



# In[ ]:


def make_do_params(all_params,verbose=False):
    do_params=[]
    for p in all_params:
        if os.path.exists(p.sfname):
            if verbose:
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


def run_one_fix(params,overwrite=False):
    import plasticnet as pn
    count,eta,noise,number_of_neurons,sfname=(params.count,params.eta,params.noise,
                                        params.number_of_neurons,params.sfname)

    if not overwrite and os.path.exists(sfname):
        return sfname

    seq=pn.Sequence()

    t=8*day
    ts=1*hour

    # DEBUG
    if _debug:
        t=1*minute
        ts=1*second

    seq+=deficit(total_time=t,
           save_interval=ts)

    t=16*hour*7*2
    ts=1*hour

    # DEBUG
    if _debug:
        t=1*minute
        ts=1*second

    seq+=fix(total_time=t,
           save_interval=ts,
             eta=eta,noise=noise)

    seq.run(display_hash=False)
    pn.save(sfname,seq) 

    return sfname



# In[ ]:


def run_one_blur(params):
    import plasticnet as pn
    count,blur,noise,number_of_neurons,sfname=(params.count,params.blur,params.noise,
                                        params.number_of_neurons,params.sfname)

    seq=pn.Sequence()

    t=8*day
    ts=1*hour

    if _debug:
        t=1*minute
        ts=1*second

    seq+=deficit(total_time=t,
           save_interval=ts)

    t=16*hour*7*2 
    ts=1*hour

    if _debug:
        t=1*minute
        ts=6*second

    seq+=treatment(blur=blur,
                   noise=0.1,
                   noise2=noise,  # treated (strong-eye) noise
                   total_time=t,
                   eta=1e-6,
                   save_interval=ts)


    seq.run(display_hash=False)
    pn.save(sfname,seq) 

    return sfname


def run_one_patch(params):
    import plasticnet as pn
    count,noise,number_of_neurons,sfname=(params.count,params.noise,
                                        params.number_of_neurons,params.sfname)

    seq=pn.Sequence()

    t=8*day
    ts=1*hour

    if _debug:
        t=1*minute
        ts=1*second

    seq+=deficit(total_time=t,
           save_interval=ts)

    # treatment 1
    t1=6*hour 
    ts1=1*hour

    # treatment 2
    t2=10*hour
    ts2=1*hour

    if _debug:
        # treatment 1
        t1=10*second
        ts1=1*second

        # treatment 2
        t1=10*second
        ts1=1*second

    for i in range(7*2):  # two weeks, 6 hours per day for patch

        seq+=patch_treatment(patch_noise=noise,
                       eta=1e-6,
                       total_time=t1,
                       save_interval=ts1)
        seq+=fix(total_time=t2,
                   eta=1e-6,
                    save_interval=ts2)

    seq.run(display_hash=False,print_time=True)
    pn.save(sfname,seq) 

    return sfname



# In[ ]:


def run_one_mask(params):
    import plasticnet as pn
    count,contrast,mask,f,number_of_neurons,sfname=(params.count,params.contrast,params.mask,params.f,
                                        params.number_of_neurons,params.sfname)

    seq=pn.Sequence()

    t=8*day
    ts=1*hour

    if _debug:
        t=1*minute
        ts=1*second

    seq+=deficit(total_time=t,
           save_interval=ts)

    # treatment 1
    t1=6*hour 
    ts1=1*hour

    # treatment 2
    t2=10*hour
    ts2=1*hour

    if _debug:
        # treatment 1
        t1=10*second
        ts1=1*second

        # treatment 2
        t1=10*second
        ts1=1*second

    for i in range(7*2):  # two weeks, 6 hours per day for VR

        seq+=treatment(f=f,
                       mask=mask,
                       contrast=contrast,
                       eta=1e-6,
                       total_time=t1,
                       save_interval=ts1)
        seq+=fix(total_time=t2,
                   eta=1e-6,
                    save_interval=ts2)

    seq.run(display_hash=False,print_time=True)
    pn.save(sfname,seq) 


    return sfname


def run_one_half_continuous_mask(params,overwrite=False):
    import plasticnet as pn
    count,contrast,mask,f,number_of_neurons,sfname=(params.count,params.contrast,params.mask,params.f,
                                        params.number_of_neurons,params.sfname)

    if not overwrite and os.path.exists(sfname):
        return sfname


    seq=pn.Sequence()

    t=8*day
    ts=1*hour

    if _debug:
        t=1*minute
        ts=1*second

    seq+=deficit(total_time=t,
           save_interval=ts)

    # treatment 1 - contrast/mask
    t1=16*hour 
    ts1=1*hour

    # treatment 2 - fix
    t2=8*hour 
    ts2=1*hour

    if _debug:
        # treatment 1
        t1=10*second
        ts1=1*second

        # treatment 2
        t2=10*second
        ts2=1*second

    for i in range(7*2):  # two weeks, 6 hours per day for VR

        seq+=treatment(f=f,
                       mask=mask,
                       contrast=contrast,
                       eta=1e-6,
                       total_time=t1,
                       save_interval=ts1)
        seq+=fix(total_time=t2,
                   eta=1e-6,
                    save_interval=ts2)



    seq.run(display_hash=False,print_time=True)
    pn.save(sfname,seq) 


    return sfname




def run_one_continuous_mask(params,overwrite=False):
    import plasticnet as pn
    count,contrast,mask,f,number_of_neurons,sfname=(params.count,params.contrast,params.mask,params.f,
                                        params.number_of_neurons,params.sfname)

    if not overwrite and os.path.exists(sfname):
        return sfname


    seq=pn.Sequence()

    t=8*day
    ts=1*hour

    if _debug:
        t=1*minute
        ts=1*second

    seq+=deficit(total_time=t,
           save_interval=ts)

    # treatment 1
    t1=16*hour 
    ts1=1*hour

    if _debug:
        # treatment 1
        t1=10*second
        ts1=1*second

        # treatment 2
        t2=10*second
        ts2=1*second

    for i in range(7*2):  # two weeks, 6 hours per day for VR

        seq+=treatment(f=f,
                       mask=mask,
                       contrast=contrast,
                       eta=1e-6,
                       total_time=t1,
                       save_interval=ts1)

    seq.run(display_hash=False,print_time=True)
    pn.save(sfname,seq) 


    return sfname




# In[5]:


def savefig(origfname):
    dirname1,fname1=os.path.split(origfname)
    base,ext=os.path.splitext(fname1)
    import matplotlib.pyplot as plt

    dirname1=dirname1.replace("/",'-')
    if dirname1:
        print_fnames=[f'Manuscript/resources/{dirname1}-{base}.png',f'Manuscript/resources/{dirname1}-{base}.svg']
    else:
        print_fnames=[f'Manuscript/resources/{base}.png',f'Manuscript/resources/{base}.svg']
    if ext:
        if ext!='.png' and ext!='.svg':
            if dirname1:
                print_fnames+=[origfname,f'Manuscript/resources/{dirname1}-{base}{ext}']
            else:
                print_fnames+=[origfname,f'Manuscript/resources/{base}{ext}']

    for fname in print_fnames:
        print(fname)
        plt.savefig(fname, bbox_inches='tight', transparent=True)


# In[8]:


#savefig('test/hello.pdf')


# In[2]:


import os
os.path.splitext('hello.txt')


# In[ ]:


# def mydisplay(t,sim,neurons,connections):
#     global _fig
#     from IPython.display import display, clear_output
#     from pylab import figure,close,gcf
#     try:
#         clear_output(wait=True)

#         _fig=pn.utils.plot_rfs_and_theta(sim,neurons,connections)
#         _fig.suptitle("%.2f" % (t/hour))
#         display(_fig)
#         close(_fig)
#     except KeyboardInterrupt:
#         close(_fig)
#         raise


# In[ ]:


def blur_jitter_deficit(blur=[2.5,-1],
                        noise=[0.1,.1],
                        rf_size=19,eta=2e-6,
                        mu_c=0,sigma_c=0,    
                        mu_r=0,sigma_r=0,
                        number_of_neurons=10,
                        total_time=8*day,
                        save_interval=1*hour):

    base_image_file='asdf/bbsk081604_all.asdf'

    if _debug:
        total_time=1*minute
        save_interval=1*second

    images=[]
    dt=200*ms

    print(base_image_file)

    for bv in blur:
        if bv<=0:
            im=pi5.filtered_images(
                                base_image_file,
                                {'type':'Rtodog','sd1':1,'sd2':3},
                                )
        else:
            im=pi5.filtered_images(
                                    base_image_file,
                                    {'type':'blur','size':bv},
                                    {'type':'Rtodog','sd1':1,'sd2':3},
                                    )
        images.append(im)


    dt=200*ms        
    pre1=pn.neurons.natural_images_with_jitter(images[0],
                                                rf_size=rf_size,
                                                time_between_patterns=dt,
                                                sigma_r=0,
                                                sigma_c=0,
                                                buffer_c=mu_c+2*sigma_c,
                                                buffer_r=mu_r+2*sigma_r,
                                                verbose=False)

    pre2=pn.neurons.natural_images_with_jitter(images[1],
                                                rf_size=rf_size,
                                                other_channel=pre1,
                                                time_between_patterns=dt,
                                                mu_r=mu_r,mu_c=mu_c,
                                                sigma_r=sigma_r,sigma_c=sigma_c,
                                                verbose=False)



    sigma=noise
    pre1+=pn.neurons.process.add_noise_normal(0,sigma)

    sigma=noise
    pre2+=pn.neurons.process.add_noise_normal(0,sigma)

    pre=pre1+pre2

    post=default_post(number_of_neurons)
    c=default_bcm(pre,post)
    c.eta=eta

    sim=pn.simulation(total_time)
    sim.dt=dt

    sim.monitor(post,['output'],save_interval)
    sim.monitor(c,['weights','theta'],save_interval)

    sim+=pn.grating_response(print_time=False)

    return sim,[pre,post],[c]


# In[ ]:


def fix_jitter(noise=0.1,rf_size=19,
           number_of_neurons=10,
            mu_c=0,sigma_c=0,    
            mu_r=0,sigma_r=0,
           total_time=8*day,
           save_interval=1*hour,
           eta=2e-6):

    if _debug:
        total_time=1*minute
        save_interval=1*second
    base_image_file='asdf/bbsk081604_all.asdf'

    print(base_image_file)

    im=pi5.filtered_images(
                        base_image_file,
                        {'type':'Rtodog','sd1':1,'sd2':3},
                        )

    dt=200*ms        
    pre1=pn.neurons.natural_images_with_jitter(im,
                                                rf_size=rf_size,
                                                time_between_patterns=dt,
                                                sigma_r=0,
                                                sigma_c=0,
                                                buffer_c=mu_c+2*sigma_c,
                                                buffer_r=mu_r+2*sigma_r,
                                                verbose=False)
    pre2=pn.neurons.natural_images_with_jitter(im,
                                                rf_size=rf_size,
                                                other_channel=pre1,
                                                time_between_patterns=dt,
                                                mu_r=mu_r,mu_c=mu_c,
                                                sigma_r=sigma_r,sigma_c=sigma_c,
                                                verbose=False)


    sigma=noise
    pre1+=pn.neurons.process.add_noise_normal(0,sigma)

    sigma=noise
    pre2+=pn.neurons.process.add_noise_normal(0,sigma)

    pre=pre1+pre2

    post=default_post(number_of_neurons)
    c=default_bcm(pre,post)
    c.eta=eta

    save_interval=save_interval

    sim=pn.simulation(total_time)
    sim.dt=dt

    sim.monitor(post,['output'],save_interval)
    sim.monitor(c,['weights','theta'],save_interval)

    sim+=pn.grating_response(print_time=False)

    return sim,[pre,post],[c]


# In[ ]:


def treatment_jitter(contrast=1,noise=0.1,noise2=0.1,
              rf_size=19,eta=5e-6,
              f=30,  # size of the blur for mask, which is a measure of overlap
            mu_c=0,sigma_c=0,    
            mu_r=0,sigma_r=0,
           number_of_neurons=20,
           total_time=8*day,
           save_interval=1*hour,
             mask=None,
             blur=0):

    if _debug:
        total_time=1*minute
        save_interval=1*second
    base_image_file='asdf/bbsk081604_all.asdf'

    im=pi5.filtered_images(
                        base_image_file,
                        {'type':'Rtodog','sd1':1,'sd2':3},
                        )
    dt=200*ms        

    if not f in [10,30,50,70,90]:
        raise ValueError("Unknown f %s" % str(f))

    if mask:
        if blur:
            maskA_fname=pi5.filtered_images(im,
                                        {'type':'blur','size':blur},
                                        {'type':'mask',
                                         'name':'bblais-masks-20210615/2021-06-15-*-A-fsig%d.png'% f, 
                                        'seed':101},
                                            verbose=False,
                                      )
            maskF_fname=pi5.filtered_images(im,
                                        {'type':'blur','size':blur},
                                        {'type':'mask',
                                         'name':'bblais-masks-20210615/2021-06-15-*-F-fsig%d.png' % f, 
                                        'seed':101},
                                            verbose=False,
                                      )            
        else:
            maskA_fname=pi5.filtered_images(im,
                                        {'type':'mask',
                                         'name':'bblais-masks-20210615/2021-06-15-*-A-fsig%d.png' % f,
                                        'seed':101},
                                            verbose=False,
                                      )
            maskF_fname=pi5.filtered_images(im,
                                        {'type':'mask',
                                         'name':'bblais-masks-20210615/2021-06-15-*-F-fsig%d.png' % f,
                                        'seed':101},
                                            verbose=False,
                                      )

        pre1=pn.neurons.natural_images_with_jitter(maskA_fname,
                                                   rf_size=rf_size,
                                                time_between_patterns=dt,
                                                sigma_r=0,
                                                sigma_c=0,
                                                buffer_c=mu_c+2*sigma_c,
                                                buffer_r=mu_r+2*sigma_r,
                                    verbose=False)
        pre2=pn.neurons.natural_images_with_jitter(maskF_fname,rf_size=rf_size,
                                    other_channel=pre1,
                                    mu_r=mu_r,mu_c=mu_c,
                                    sigma_r=sigma_r,sigma_c=sigma_c,
                                    verbose=False)

    else:

        if blur:
            blur_fname=pi5.filtered_images(im,
                                        {'type':'blur','size':blur},
                                            verbose=False,
                                          )

        norm_fname=pi5.filtered_images(im,
                                            verbose=False,
                                      )


        pre1=pn.neurons.natural_images_with_jitter(norm_fname,rf_size=rf_size,
                                                time_between_patterns=dt,
                                                sigma_r=0,
                                                sigma_c=0,
                                                buffer_c=mu_c+2*sigma_c,
                                                buffer_r=mu_r+2*sigma_r,
                                    verbose=False)

        if blur:
            pre2=pn.neurons.natural_images_with_jitter(blur_fname,rf_size=rf_size,
                                        other_channel=pre1,
                                    mu_r=mu_r,mu_c=mu_c,
                                    sigma_r=sigma_r,sigma_c=sigma_c,
                                        verbose=False)
        else:
            pre2=pn.neurons.natural_images_with_jitter(norm_fname,rf_size=rf_size,
                                        other_channel=pre1,
                                    mu_r=mu_r,mu_c=mu_c,
                                    sigma_r=sigma_r,sigma_c=sigma_c,
                                        verbose=False)



    sigma=noise
    pre1+=pn.neurons.process.add_noise_normal(0,sigma)

    sigma=noise2
    pre2+=pn.neurons.process.scale_shift(contrast,0)
    pre2+=pn.neurons.process.add_noise_normal(0,sigma)

    pre=pre1+pre2

    post=pn.neurons.linear_neuron(number_of_neurons)
    post+=pn.neurons.process.sigmoid(-1,50)

    c=pn.connections.BCM(pre,post,[-.1,.1],[.1,.2])
    c.eta=eta
    c.tau=100*second

    save_interval=save_interval

    sim=pn.simulation(total_time)

    sim.dt=dt

    sim.monitor(post,['output'],save_interval)
    sim.monitor(c,['weights','theta'],save_interval)

    sim+=pn.grating_response(print_time=False)

    return sim,[pre,post],[c]

def patch_treatment_jitter(noise=0.1,patch_noise=0.1,rf_size=19,
                   number_of_neurons=20,
                    mu_c=0,sigma_c=0,    
                    mu_r=0,sigma_r=0,
                   total_time=8*day,
                   save_interval=1*hour,
                   eta=2e-6,
                   ):

    if _debug:
        total_time=1*minute
        save_interval=1*second
    base_image_file='asdf/bbsk081604_all.asdf'

    im=pi5.filtered_images(
                        base_image_file,
                        {'type':'Rtodog','sd1':1,'sd2':3},
                        )
    dt=200*ms        

    norm_fname=pi5.filtered_images(im,
                                verbose=False
                                  )


    pre1=pn.neurons.natural_images_with_jitter(norm_fname,rf_size=rf_size,
                                                time_between_patterns=dt,
                                                sigma_r=0,
                                                sigma_c=0,
                                                buffer_c=mu_c+2*sigma_c,
                                                buffer_r=mu_r+2*sigma_r,
                                verbose=False)

    pre2=pn.neurons.natural_images_with_jitter(norm_fname,rf_size=rf_size,
                                other_channel=pre1,
                                time_between_patterns=dt,
                                mu_r=mu_r,mu_c=mu_c,
                                sigma_r=sigma_r,sigma_c=sigma_c,
                                verbose=False)



    sigma=noise
    pre1+=pn.neurons.process.add_noise_normal(0,sigma)

    sigma=patch_noise
    pre2+=pn.neurons.process.scale_shift(0.0,0) # zero out signal
    pre2+=pn.neurons.process.add_noise_normal(0,sigma)

    pre=pre1+pre2

    post=default_post(number_of_neurons)
    c=default_bcm(pre,post)
    c.eta=eta

    save_interval=save_interval

    sim=pn.simulation(total_time)

    sim.dt=dt

    sim.monitor(post,['output'],save_interval)
    sim.monitor(c,['weights','theta'],save_interval)

    sim+=pn.grating_response(print_time=False)

    return sim,[pre,post],[c]


# In[ ]:


def seq_load(seq,fname):
    s,n,c=seq.sims[0],seq.neurons[0],seq.connections[0]

    assert len(c)==1,"Need to implement more then one connection"
    with asdf.open(fname) as af:
        L=af.tree['attrs']['sequence length']
        i=L-1  # last one
        m=af.tree['sequence %d' % i]['connection 0']['monitor weights'] 
        t,W=m['t'],m['values']
        W=np.array(W)
        t=np.array(t)


        m=af.tree['sequence %d' % i]['connection 0']['monitor theta']           
        t,theta=m['t'],m['values']
        theta=np.array(theta)

        c[0].initial_weights=W[-1]
        c[0].reset_to_initial=True
        c[0].initial_theta=theta[-1]        
        c[0]._reset()



# In[ ]:


