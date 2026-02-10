import time
import datetime
from datetime import datetime

import numpy as np
import scipy as sci
from scipy import stats, signal
from scipy.stats import norm
#import allantools

import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('SVG')

from io import StringIO

def plot2svg(fig, transparent=False,  **kwargs):
    #https://stackoverflow.com/questions/5453375/matplotlib-svg-as-string-and-not-a-file
    imgdata = StringIO()
    fig.savefig(imgdata, format='svg', bbox_inches='tight', transparent=transparent, **kwargs)
    imgdata.seek(0)  # rewind the data
    svg_data = imgdata.getvalue()  # this is svg data
    imgdata.close()
    svg_data = svg_data.replace('white-space:pre;','')
    return svg_data

def parse_data(t_list, y_list, e_list, o_list):
    if len(t_list) == len(y_list):
        t = np.array(t_list)
        if len(t)>0:
            t = (t-t[0])
            y_input = np.array(y_list)
            y_outpt = np.array(o_list)
            y_error = np.array(e_list)
            return t, y_input, y_error, y_outpt
    return None

def plot_mpl(name, t, y, o, e, setpoint, setpoint_tolerance, this_conf):
    lbl_in = this_conf['unit_input']
    lbl_out = this_conf['unit_output']
    
    fig, (ax1, ax3) = plt.subplots(2, sharex=True, sharey=False, figsize=(10.,8.))
    
    ax1.set_ylabel(lbl_in)
    lns1 = ax1.plot(t,y,'.--',color='C0', label='Input')

    ax2 = ax1.twinx()
    ax2.set_ylabel(lbl_out)
    lns2 = ax2.plot(t,o,'.--',color='C1', label='Output')

    ax1.set_ylabel(lbl_in)
    lns4 = ax1.plot(t,setpoint,'.--',color='C3', label='Setpoint') 

    if setpoint_tolerance is not None:
        SetpointsUpperLimit = np.array(setpoint) + setpoint_tolerance
        Setpoints_LowerLimit = np.array(setpoint) - setpoint_tolerance
        ax1.fill_between(
            t,
            Setpoints_LowerLimit,
             SetpointsUpperLimit,
            color='C3',
            alpha=0.2,      # Transparenz
            label='Tolerance'
        )   
    
    # added plots to legend
    lns = lns1+lns2+lns4
    labs = [l.get_label() for l in lns]
    if setpoint_tolerance is not None:
        labs.append(f'±{setpoint_tolerance*10**6} MHz Tolerance')
        # Dummy-Handle für den Toleranz-Eintrag in der Legende
        from matplotlib.patches import Patch
        lns.append(Patch(color='C3', alpha=0.2))
    ax1.legend(lns, labs, loc=0)    
    ax1.legend(lns, labs, loc=0)

    ax3.set_xlabel('Time (s)')
    ax3.set_ylabel(lbl_in)
    ax3.plot(t,e,'.--',color='C2', label='Error')
    ax3.legend()

    return fig

def plot_mpl_log(name, t, y, o, e, this_conf):
    lbl_in = this_conf['unit_input']
    lbl_out = this_conf['unit_output']
    
    fig, ax1 = plt.subplots(1, sharex=True, sharey=False, figsize=(10.,4.))
    
    ax1.ticklabel_format(useOffset=False, style='plain')
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel(lbl_in)
    lns1 = ax1.plot(t,y,'.--',color='C0', label='Input')

    # added plots to legend
    lns = lns1
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, loc=0)

    return fig


def plt_time_series(data, lbl=['Duration (s)','RF pwr. (a.u.)']):
    sns.set(font_scale=0.85)
    x, y, yerr = data
    smpl_rate=((x[-1]-x[0])/len(x))**(-1)
    slope, intercept, r_value, p_value, std_err = stats.linregress(x,y)
    txt = 'Total dur. (min): '+str(round((x[-1]-x[0])/60,1))+' / Sample size: '+str(len(y))+''
    #txt += '\nDrift: '+ self.prnt_rslts('d/dt', slope*60*1e3, std_err*60*1e3, verbose=False)+'$\,\cdot\,10^{-3}$ min$^{-1}$'
    #time series
    plt.errorbar(x, y, yerr=yerr, linestyle='', marker='o', color='navy', alpha=.5)
    sns.regplot(x, y, color='red')
    #plt.legend()
    plt.title(txt)
    plt.xlabel(lbl[0])
    plt.ylabel(lbl[1])

    #PSD
    plt.axes([.95,.58,.3,.295])
    f, psd = signal.periodogram(y, smpl_rate)
    plt.semilogy(f, psd, color='navy')
    #plt.ylim([1e19*np.min(psd), 10.*np.max(psd)])
    plt.xlabel('Freq. (Hz)')
    plt.ylabel('PSD (a.u.)')
    plt.yticks([])

    #distribution
    try:
        plt.axes([.95,0.125,.3,.295])
        sns.distplot(y, kde=False, fit=sci.stats.norm, label='$\Delta$='+str(round(np.std(y),7)), color='navy')
        plt.legend(loc='lower center')
        plt.axvline(x=np.mean(y), color='red')
        plt.yticks([])
        plt.xticks([np.mean(y)])
        plt.xlabel(lbl[1])
        plt.ylabel('Prop.')
    except LinAlgError:
        pass
    return plt.gcf()
    #self.eval_oadev(y, smpl_rate, lbl=lbl[1][:-5], units='', show_ref='None', scl_ref=1, verbose=True, rel=1)

def plot_type_log(ch, t_str, t, y0, this_conf):
    fig, ax1 = plt.subplots(figsize=(5., 2.))
    ax1.plot(t/3600, y0, color='navy')
    ax1.set_xlabel('Log duration (h)')
    ax1.set_ylabel(this_conf['unit_input'])
    plt.title(ch+' ('+str(t_str)+')'+'\nMean: '+str(round(np.mean(y0),1)))
    #fig.tight_layout()
    return fig

def plot_type_lock_euro(ch, t_str, t, y, y0, y1, this_conf):
    return plt_time_series((t, y0, y0*0.), lbl=['Duration (s)',this_conf['unit_input']])

def plot_type_lock(ch, t_str, t, y, y0, y1, this_conf):
    sns.set(font_scale=0.75)
    
    lbl_in = this_conf['unit_input']
    lbl_out = this_conf['unit_output']
    stat_lock = this_conf['lock']
    stat_active = this_conf['active']
    setpoint = this_conf['setpoint']
    limits = this_conf['limits']
    offset = this_conf['offset']
    
    fig, ax1 = plt.subplots(figsize=(5., 2.))
    
    ax1.plot(t, y0, color='navy')
    ax1.set_xlabel('Log duration (min)')
    ax1.set_ylabel(lbl_in, color='navy')
    ax1.tick_params('y', colors='navy')

    textst='Act: '+str(stat_active)
    textst+='\nLck: '+str(stat_lock)
    textst+='\n\nSet (THz): '+str(setpoint)
    textst+='\nLim (V): '+str(np.array(limits)+offset)
    ax1.text(1.2, 1., textst, transform=ax1.transAxes, fontsize=8, verticalalignment='top')
    
    ax2 = ax1.twinx()
    ax2.plot(t, y1, color='red')
    ax2.set_ylabel(lbl_out, color='red')
    ax2.tick_params('y', colors='red')
    plt.grid(False)
    
    t_ts = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(t[0]))
    plt.title(ch+' ('+str(t_str)+')'+'\nMean (THz): '+str(round(np.mean(y),6)))
    
    if len(t)>10:
        ''''''
        mu, std = norm.fit(y0)
        xmin=mu-2.5*std
        xmax=mu+2.5*std
        x = np.linspace(xmin, xmax, 100)
        p = norm.pdf(x, mu, std)
        plt.axes([1.075, .13, .25, .30])
        plt.hist(y0, bins = int(2*np.log(len(y0))), density=True, color='navy', edgecolor='white')
        plt.plot(x, p, color='red', linewidth=3, alpha=0.75)
        plt.axvline(x=0, linewidth=5, color='green', alpha=0.5)
        plt.xlim((xmin, xmax))
        plt.xlabel('Freq. dev. (MHz)')
        plt.ylabel('Prop.')
        plt.title('std = '+str(round(std, 2))+' MHz')
        plt.yticks([])
        
    #fig.tight_layout()
    return fig

def plot_data(name, t0, this_conf, t, y_input, y_error, y_outpt, setpoint, setpoint_tolerance):
    lock_type = this_conf['type']
    t_str = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(t0))
    if (lock_type>0):
        #fig = plot_type_lock(name, t_str, t, y_input, y_error, y_outpt, this_conf)
        #fig = plot_type_lock_euro(name, t_str, t, y_input, y_error, y_outpt, this_conf)
        fig = plot_mpl(name, t, y_input, y_outpt, y_error, setpoint, setpoint_tolerance, this_conf)
    else:
        #fig = plot_type_log(name, t_str, t, y_input, this_conf)
        fig = plot_mpl_log(name, t, y_input, y_outpt, y_error, this_conf)

    return fig

def export_plot_svg(fig, **kwargs):
    #plt.show()
    svg_dta = plot2svg(fig, **kwargs)
    plt.close(fig=fig)
    return svg_dta
