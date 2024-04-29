import sys
import copy
import numpy
from Waitbar import Waitbar
import array
from PIL import Image
# for difference of gaussians (dog)
import scipy.signal as sig

# for the olshausen images
from scipy.io import loadmat

# for whitening
from scipy.fftpack import fft2, fftshift, ifft2, ifftshift
from scipy import real,absolute

def image2array(im):
    if im.mode not in ("L", "F"):
        raise ValueError( "can only convert single-layer images")
    if im.mode == "L":
        a = numpy.frombytes(im.tobytes(), numpy.uint8)
    else:
        a = numpy.frombytes(im.tobytes(), numpy.float32)
    a.shape = im.size[1], im.size[0]
    return a

def array2image(a):
    if a.dtype.name == 'uint8':
        mode = "L"
    elif a.dtype.name == 'float32':
        mode = "F"
    elif a.dtype.name == 'float64':
        a=a.astype('float32')
        mode = "F"
    else:
        raise ValueError("unsupported image mode %s" % a.dtype.name)
    return Image.frombytes(mode, (a.shape[1], a.shape[0]), a.tobytes())




    
def dog(sd1,sd2,size):
    
    v1=numpy.floor((size-1.0)/2.0)
    v2=size-1-v1
    
    y,x=numpy.mgrid[-v1:v2,-v1:v2]
    
    pi=numpy.pi
    
    # raise divide by zero error if sd1=0 and sd2=0
    
    if sd1>0:
        g=1./(2*pi*sd1*sd1)*numpy.exp(-x**2/2/sd1**2 -y**2/2/sd1**2)
        if sd2>0:
            g=g- 1./(2*pi*sd2*sd2)*numpy.exp(-x**2/2/sd2**2 -y**2/2/sd2**2)
    else:
        g=- 1./(2*pi*sd2*sd2)*numpy.exp(-x**2/2/sd2**2 -y**2/2/sd2**2)
    
    return g

def dog_filter(A,sd1=1,sd2=3,size=None,shape='valid',surround_weight=1):
    
    if not size:
        size=2.0*numpy.ceil(2.0*max([sd1,sd2]))+1.0
        
    if sd1==0 and sd2==0:
        B=copy.copy(A)
        return B
    
    g=dog(sd1,sd2,size)

    B=sig.convolve2d(A,g,mode=shape)
    
    return B


def make_scale_shift(var,scale=1.0,shift=0.0,truncate=False,verbose=True):
    im2_list=[]
    
    im_scale_shift=var['im_scale_shift']
    im_count=len(var['im'])
    if verbose:
        w = Waitbar(True)
    for count,im in enumerate(var['im']):
        im2=im*im_scale_shift[0]+im_scale_shift[1]
        
        im2=im2*scale+shift
        if truncate:
            im2[im2<0]=0.0
        
        if count==0 and verbose:
            print( "Scale Shift %.1f,%.1f" % (scale,shift))
        im2_list.append(im2)
        
        if verbose:
            w.updated((count+1)/float(im_count))
    
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    if verbose:
        print()
    return var2    

    
    
# this one seems to ignore the standard scale shift
def scale_shift(var,scale=1.0,shift=0.0,truncate=False,verbose=True):
    im2_list=[]
    
    im_scale_shift=var['im_scale_shift']
    im_count=len(var['im'])
    if verbose:
        w = Waitbar(True)
    for count,im in enumerate(var['im']):
        im2=im.copy()
        
        im2=im2*scale+shift
        if truncate:
            im2[im2<0]=0.0
        
        if count==0 and verbose:
            print( "Scale Shift %.1f,%.1f" % (scale,shift))
        im2_list.append(im2)
        
        if verbose:
            w.updated((count+1)/float(im_count))
    
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    if verbose:
        print()
    return var2

def apply_mask(var,mask_name):
    from PIL import Image
    from pylab import array,randint

    im2_list=[]
    
    im_scale_shift=var['im_scale_shift']
    
    im_count=len(var['im'])
    
    w = Waitbar(True)
    im1=var['im'][0]

    for count,im in enumerate(var['im']):

        if isinstance(mask_name,list):
            im_A=Image.open(mask_name[count])
        else:
            im_A=Image.open(mask_name)
        A=array(im_A)


        im2=im*im_scale_shift[0]+im_scale_shift[1]
        
        #r,c=randint(A.shape[0]-im1.shape[0]),randint(A.shape[1]-im1.shape[1])
        r,c=0,0
        alpha_A=A[(0+r):(im1.shape[0]+r),(0+c):(im1.shape[1]+c),3]/255
        
        
        
        im2=im2*alpha_A

        if count==0:
            print( "Mask %s" % (mask_name))

        im2_list.append(im2)
        
        w.updated((count+1)/float(im_count))
    
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    print()
    return var2


def make_norm(var,mu=0,sd=1,subtract_mean=True,verbose=True):
    
    im2_list=[]
    
    im_scale_shift=var['im_scale_shift']
    
    im_count=len(var['im'])
    
    if verbose:
        w = Waitbar(True)
    for count,im in enumerate(var['im']):
        im2=im.copy()
        
        if subtract_mean:
            im2=im2-im2.mean()
            
        im2=im2/im2.std()
        
        if count==0:
            if verbose:
                print( "Norm %.1f,%.1f" % (mu,sd))
                
        im2_list.append(im2)
        
        if verbose:
            w.updated((count+1)/float(im_count))
    
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    if verbose:
        print()
    return var2

def make_Rtodog(var,sd1=1,sd2=3,size=32,shape='valid',verbose=True):
    from numpy import log2

    im2_list=[]
    
    im_scale_shift=var['im_scale_shift']
    
    im_count=len(var['im'])
    if verbose:
        w = Waitbar(True)
        w.message="Photoreceptor then Difference of Gaussians"
    for count,im in enumerate(var['im']):
        orig_size=im.shape

        im=im*im_scale_shift[0]+im_scale_shift[1]
        im=im/(im.mean()+im)

        im2=dog_filter(im,sd1,sd2,size,shape)
        new_size=im2.shape
        
        im2=im2-im2.mean()
        im2=im2/im2.std()
        
        if count==0 and verbose:
            print( "Dog %d,%d: %dx%d --> %dx%d" % (sd1,sd2,
                                                            orig_size[0],orig_size[1],
                                                            new_size[0],new_size[1]))
        im2_list.append(im2)
        
        if verbose:
            w.updated((count+1)/float(im_count))
    
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    if verbose:
        print()
    return var2



def make_log2dog(var,sd1=1,sd2=3,size=32,shape='valid',verbose=True):
    from numpy import log2

    im2_list=[]
    
    im_scale_shift=var['im_scale_shift']
    
    im_count=len(var['im'])
    if verbose:
        w = Waitbar(True)
        w.message="Log then Difference of Gaussians"
    for count,im in enumerate(var['im']):
        orig_size=im.shape

        im=im*im_scale_shift[0]+im_scale_shift[1]
        im=log2(im-im.min()+1)

        im2=dog_filter(im,sd1,sd2,size,shape)
        new_size=im2.shape
        
        im2=im2-im2.mean()
        im2=im2/im2.std()
        
        if count==0 and verbose:
            print( "Dog %d,%d: %dx%d --> %dx%d" % (sd1,sd2,
                                                            orig_size[0],orig_size[1],
                                                            new_size[0],new_size[1]))
        im2_list.append(im2)
        
        if verbose:
            w.updated((count+1)/float(im_count))
    
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    if verbose:
        print()
    return var2

def make_dog(var,sd1=1,sd2=3,size=32,shape='valid',verbose=True):
    
    im2_list=[]
    
    im_scale_shift=var['im_scale_shift']
    
    im_count=len(var['im'])
    
    if verbose:
        w = Waitbar(True)
        w.message="Difference of Gaussians"
    for count,im in enumerate(var['im']):
        orig_size=im.shape
        im2=dog_filter(im*im_scale_shift[0]+im_scale_shift[1],sd1,sd2,size,shape)
        new_size=im2.shape
        
        im2=im2-im2.mean()
        im2=im2/im2.std()
        
        if count==0 and verbose:
            print( "Dog %d,%d: %dx%d --> %dx%d" % (sd1,sd2,
                                                            orig_size[0],orig_size[1],
                                                            new_size[0],new_size[1]))
        im2_list.append(im2)
        
        if verbose:
            w.updated((count+1)/float(im_count))
    
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    if verbose:
        print()
    return var2

def make_white(var,verbose=True):
    
    im_scale_shift=var['im_scale_shift']
    im2_list=[]
    
    
    im_count=len(var['im'])
    
    w = Waitbar(True)
    w.message="Whitening"
    for count,im in enumerate(var['im']):
    
        im=im-im.mean()+1  # add a little DC to get rid of nans
    
        yf=fftshift(fft2(im*im_scale_shift[0]+im_scale_shift[1]))
        fl=1.0/absolute(yf)
        
        yffl=yf*fl;  
        im2=real(ifft2(ifftshift(yffl)))
        
        im2=im2-im2.mean()
        im2=im2/im2.std()

        if count==0:
            print( "Whiten.")
        im2_list.append(im2)
    
        w.updated((count+1)/float(im_count))

    print()
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    return var2


    
def make_rot(var,which_angles,more=False,verbose=True):
    
    def radians(deg):
        return deg*numpy.pi/180.0
    
    im_scale_shift=var['im_scale_shift']
    im2_list=[]
    

    for a in which_angles:
        print( "Rotate ",a)
        im_count=len(var['im'])
        
        w = Waitbar(True)
        w.message="Rotating"
        for count,imm in enumerate(var['im']):
            im=imm*im_scale_shift[0]+im_scale_shift[1]
            
            orig_size=im.shape
            im=im[:,:orig_size[0]]  # crop to square
            sz=im.shape
            new_size=sz
            
            Im=array2image(im).rotate(a)
            im2=image2array(Im)
            
            
            # assume square images, and worst case (45 deg)
            s=sz[0]
            l=int(numpy.ceil(s/numpy.sqrt(2)))
            i1=int((s-l)/2)
            im2=im2[i1:(i1+l),i1:(i1+l)]
            
            im2=im2-im2.mean()
            im2=im2/im2.std()
    
            if count==0:
                print( "Rotate %d: %dx%d --> %dx%d" % (a,
                                                            orig_size[0],orig_size[1],
                                                            new_size[0],new_size[1]))
            im2_list.append(im2)
            
            if more:
                im=imm*im_scale_shift[0]+im_scale_shift[1]
                
                orig_size=im.shape
                im=im[:,-orig_size[0]:]  # crop to square
                sz=im.shape
                new_size=sz
                
                Im=array2image(im).rotate(a)
                im2=image2array(Im)
                
                
                # assume square images, and worst case (45 deg)
                s=sz[0]
                l=int(numpy.ceil(s/numpy.sqrt(2)))
                i1=int((s-l)/2)
                im2=im2[i1:(i1+l),i1:(i1+l)]
                
                im2=im2/im2.std()
                im2=im2-im2.mean()
        
                im2_list.append(im2)
                
                if count==0:
                    print( "Rotate more %d: %dx%d --> %dx%d" % (a,
                                                                        orig_size[0],orig_size[1],
                                                                        new_size[0],new_size[1]))
            
            
            w.updated((count+1)/float(im_count))

        print()
        
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    return var2

        

def make_pixel_shift(var,shift_x,shift_y,verbose=True):
    
    im2_list=[]
    
    im_scale_shift=var['im_scale_shift']
    
    im_count=len(var['im'])
    
    if verbose:
        w = Waitbar(True)
        w.message="Pixel Shift"
    for count,im in enumerate(var['im']):
        orig_size=im.shape
        im2=im*im_scale_shift[0]+im_scale_shift[1]
        im2=im2[shift_y:,shift_x:]
        new_size=im2.shape
        
        if verbose and count==0:
            print( "Pixel Shift %d,%d: %dx%d --> %dx%d" % (shift_x,shift_y,
                                                        orig_size[0],orig_size[1],
                                                        new_size[0],new_size[1]))
        im2_list.append(im2)
    
        if verbose:
            w.updated((count+1)/float(im_count))

    if verbose:
        print()
    
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    return var2

def add_noise(var,sd=1.0,verbose=True):
    from pylab import randn
    im2_list=[]
    
    im_scale_shift=var['im_scale_shift']
    
    im_count=len(var['im'])
    
    if verbose:
        w = Waitbar(True)
        w.message="Noise"
    for count,im in enumerate(var['im']):
        orig_size=im.shape
        im2=im*im_scale_shift[0]+im_scale_shift[1] + randn(*im.shape)*sd

        if verbose and count==0:
            print( "Noise %.3f" % (sd))

        im2_list.append(im2)
    
        if verbose:
            w.updated((count+1)/float(im_count))

    if verbose:
        print()
    
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    return var2


def make_blur(var,sd=1.0,radius=None,verbose=True):
    
    if not radius:
        radius=sd*3.0
    
    im2_list=[]
    
    im_scale_shift=var['im_scale_shift']
    
    im_count=len(var['im'])
    
    if verbose:
        w = Waitbar(True)
        w.message="Blur"
    for count,im in enumerate(var['im']):
        orig_size=im.shape
        im2=dog_filter(im*im_scale_shift[0]+im_scale_shift[1],sd,0,2*radius+1,shape='same')
        new_size=im2.shape
        
        if verbose and count==0:
            print( "Blur %d,%d: %dx%d --> %dx%d" % (sd,radius,
                                                        orig_size[0],orig_size[1],
                                                        new_size[0],new_size[1]))
        im2_list.append(im2)
    
        if verbose:
            w.updated((count+1)/float(im_count))

    if verbose:
        print()
    
    var2={'im':im2_list,'im_scale_shift':[1.0,0.0]}
    return var2

        
def set_resolution(var,resolution='uint8',verbose=True):
    
    if (var['im'][0].dtype.name==resolution):  # already there
        return
    
    sr=var['im'][0].dtype.name  # source resolution
    tr=resolution     # target resolution

    # convert to floats first
    for i in range(len(var['im'])):
        var['im'][i]=var['im'][i].astype(numpy.float)
        var['im'][i]=var['im'][i]*var['im_scale_shift'][0]+var['im_scale_shift'][1]
    var['im_scale_shift']=[1.0,0.0]
    
    if tr==numpy.float:
        return
    
    if tr=='uint8':
        maxval=255.0
    elif tr=='uint16':
        maxval=2**16-1.0
    elif tr=='float':
        return
    else:
        raise ValueError("I don't know the resolution: %s" % resolution)
    

    if verbose:
        print( "Resolution %s -> %s" % (sr,tr))
    
    mn=numpy.Inf
    mx=-numpy.Inf
    for im in var['im']:
        m=im.min()
        if m<mn:
            mn=m
        m=im.max()
        if m>mx:
            mx=m
        
    d=mx-mn   # difference between min and max
    for i in range(len(var['im'])):
        var['im'][i]=(var['im'][i]-mn)/d*maxval
        var['im'][i]=var['im'][i].astype(resolution)
        
    var['im_scale_shift']=[d/maxval, mn]
    
