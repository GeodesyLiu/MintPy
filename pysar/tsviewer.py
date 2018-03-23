#! /usr/bin/env python2
# Adopted from plotts.py from GIAnT v1.0 for PySAR products

import os
import argparse

import h5py
import numpy as np
import matplotlib.pyplot as plt
import sys
from matplotlib.widgets import Slider, Button
import scipy.stats as stats

import _datetime as ptime
import _readfile as readfile
import _pysar_utilities as ut
import view as view
from mask import mask_matrix

############# Global Variables ################
tims, inps, img, mask, d_v, d_ts = None, None, None, None, None, None
ax_v, fig_ts, fig_v, ax_ts, tslider, second_plot_axis, new_axes = None, None, None, None, None, None, None
h5, k, dateList, atr, date_num = None, None, None, None, None
lat, lon, ullat, ullon, lat_step, lon_step = None, None, None, None, None, None
width, length = None, None

plot_figure, p1_scatter, p2_scatter, scatts = None, None, None, None
p1_scatter_point, p2_scatter_point = None, None
p1_x, p1_y, p2_x, p2_y = None, None, None, None
annot = None
second_plot_axis_visible = False


###########################################################################################
def read_timeseries_yx(timeseries_file, y, x):
    '''Read time-series displacement on point (y,x) from timeseries_file
    Inputs:
        timeseries_file : string, name/path of timeseries hdf5 file
        y/x : int, row/column number of point of interest
    Output:
        dis_ts : list of float, displacement time-series of point of interest
    '''
    atr = readfile.read_attribute(timeseries_file)
    k = atr['FILE_TYPE']
    h5 = h5py.File(timeseries_file, 'r')
    date_list = list(h5[k].keys())

    dis_ts = []
    for date in date_list:
        dis_ts.append(h5[k].get(date)[y,x])
    h5.close()
    return dis_ts


def read_timeseries_lalo(timeseries_file, lat, lon):
    '''Read time-series displacement on point (y,x) from timeseries_file
    Inputs:
        timeseries_file : string, name/path of timeseries hdf5 file
        lat/lon : float, latitude/longitude of point of interest
    Output:
        dis_ts : list of float, displacement time-series of point of interest
    '''

    atr = readfile.read_attribute(timeseries_file)
    if 'X_FIRST' not in list(atr.keys()):
        print('ERROR: input file is not geocoded')
        return None

    lat0 = float(atr['Y_FIRST'])
    lat_step = float(atr['Y_STEP'])
    lon0 = float(atr['X_FIRST'])
    lon_step = float(atr['X_STEP'])
    y = int(np.rint((lat-lat0)/lat_step))
    x = int(np.rint((lon-lon0)/lon_step))
    dis_ts = read_timeseries_yx(timeseries_file, y, x)
    return dis_ts


###########################################################################################
EXAMPLE='''example:
  tsviewer.py timeseries.h5 --ylim -10 10
  tsviewer.py timeseries_demErr_plane.h5 -n 5 -m maskTempCoh.h5
  tsviewer.py timeseries_demErr_plane.h5 --yx 300 400 --nodisplay --zero-first
  tsviewer.py geo_timeseries_demErr_plane.h5 --lalo 33.250 131.665 --nodisplay
'''


def cmdLineParse(argv):
    parser = argparse.ArgumentParser(description='Interactive time-series viewer',\
                                     formatter_class=argparse.RawTextHelpFormatter,\
                                     epilog=EXAMPLE)
    parser.add_argument('timeseries_file', help='time series file to display')
    parser.add_argument('-n', dest='epoch_num', metavar='NUM', type=int, default='-2',\
                        help='Epoch/slice number to display, default: the 2nd last.')
    parser.add_argument('-m','--mask', dest='mask_file',\
                        help='mask to use. Default: geo_maskTempCoh.h5 for geocoded file and maskTempCoh.h5 for radar file')
    parser.add_argument('--error', dest='error_file', help='txt file with error for each date.')
    parser.add_argument('--dem', dest='dem_file', help='DEM file for background shaed relief')

    pixel = parser.add_argument_group('Pixel Input')
    pixel.add_argument('--yx', type=int, metavar=('Y','X'), nargs=2,\
                       help='initial pixel to plot in Y/X coord')
    pixel.add_argument('--lalo', type=float, metavar=('LAT','LON'), nargs=2,\
                       help='initial pixel to plot in lat/lon coord')
    pixel.add_argument('--ref-yx', dest='ref_yx', type=int, metavar=('Y','X'), nargs=2,\
                       help='change reference pixel to input location')
    pixel.add_argument('--ref-lalo', dest='ref_lalo', type=float, metavar=('LAT','LON'), nargs=2,\
                       help='change reference pixel to input location')

    output = parser.add_argument_group('Output Setting')
    output.add_argument('-o','--output', dest='fig_base', help='Figure base name for output files')
    output.add_argument('--save', action='store_true', dest='save_fig',\
                        help='save data and plot to files')
    output.add_argument('--nodisplay', action='store_false', dest='disp_fig',\
                        help='save data and plot to files and do not display figures\n')
    output.add_argument('--dpi', dest='fig_dpi', metavar='DPI', type=int, default=150,\
                        help='DPI - dot per inch - for display/write')

    disp = parser.add_argument_group('Display Setting')
    disp.add_argument('--figsize', dest='fig_size', metavar=('WID','LEN'), type=float, nargs=2, default=[10.0,5.0],\
                      help='Figure size in inches - width and length. Default: 10.0 5.0\n'+\
                           'i.e. 3.5 2 for ppt; ')
    disp.add_argument('--ylim', dest='ylim', nargs=2, metavar=('YMIN','YMAX'), type=float,\
                      help='Y limits for point plotting.')
    disp.add_argument('--ylim-mat', dest='ylim_mat', nargs=2, metavar=('YMIN','YMAX'), type=float,\
                      help='Display limits for matrix plotting.')
    disp.add_argument('--ref-date', dest='ref_date', help='Change reference date for display')
    disp.add_argument('--exclude','--ex', dest='ex_date_list', nargs='*', help='Exclude date shown as gray.')
    disp.add_argument('--zf','--zero-first', dest='zero_first', action='store_true',\
                      help='Set displacement at first acquisition to zero.')
    disp.add_argument('-u', dest='disp_unit', metavar='UNIT', default='cm',\
                      help='unit for display. Default: cm')
    disp.add_argument('-c','--colormap', dest='colormap', default='jet',\
                      help='colormap used for display, i.e. jet, RdBu, hsv, jet_r etc.\n'
                           'Support colormaps in Matplotlib - http://matplotlib.org/users/colormaps.html')
    disp.add_argument('-s','--fontsize', dest='font_size', type=int, default=10, help='Font size for display')
    disp.add_argument('--notitle', dest='disp_title', action='store_false', help='Do not display title in TS plot.')
    disp.add_argument('--no-flip', dest='auto_flip', action='store_false',\
                      help='Turn off auto flip based on orbit direction.\n'+\
                           'Default: flip left-right for descending data in radar coord\n'+\
                           '         flip up-down    for ascending  data in radar coord\n'+\
                           '         no flip for data in geo coord')
    disp.add_argument('--ms','--markersize', dest='marker_size', type=float, default=12.0,\
                      help='Point marker size. Default: 12.0')
    #disp.add_argument('--mc','--markercolor', dest='marker_color', default='crimson',\
    #                  help='Point marker color. Default: crimson')
    disp.add_argument('--ew','--edgewidth', dest='edge_width', type=float, default=1.0,\
                      help='Edge width. Default: 1.0')

    inps = parser.parse_args(argv)
    if (not inps.disp_fig or inps.fig_base) and not inps.save_fig:
        inps.save_fig = True
    if inps.ylim:
        inps.ylim = sorted(inps.ylim)
    return inps

################### HELPER FUNCTIONS ##########################


###################### EXTRANEOUS HELPER FUNCTIONS ######################


def display_figure():
    global inps

    if inps.disp_fig:
        plt.show()


def plot_data_from_inital_point():
    global ax_ts, inps, tims, d_ts

    if inps.yx:
        d_ts = update_timeseries(inps.yx[0], inps.yx[1], 1)
    else:
        d_ts = np.zeros(len(tims))
        ax_ts, scatter = plot_timeseries_scatter(ax_ts, d_ts, inps)


def read_error_list():
    global inps, date_num

    inps.error_ts = None
    if inps.error_file:
        error_file_content = np.loadtxt(inps.error_file, dtype=str)
        inps.error_ts = error_file_content[:, 1].astype(np.float) * inps.unit_fac
        if inps.ex_date_list:
            e_ts = inps.error_ts[:]
            inps.ex_error_ts = np.array([e_ts[i] for i in inps.ex_idx_list])
            inps.error_ts = np.array([e_ts[i] for i in range(date_num) if i not in inps.ex_idx_list])


def save_output():
    global inps, lat, lon, ullat, lat_step, ullon, lon_step, atr, fig_ts, dateList

    if inps.save_fig and inps.yx:
        print('save info for pixel ' + str(inps.yx))
        if not inps.fig_base:
            inps.fig_base = 'y%d_x%d' % (inps.yx[0], inps.yx[1])

        # TXT - point time series
        outName = inps.fig_base + '_ts.txt'
        header_info = 'timeseries_file=' + inps.timeseries_file
        header_info += '\ny=%d, x=%d' % (inps.yx[0], inps.yx[1])

        try:
            lat = ullat + inps.yx[0] * lat_step
            lon = ullon + inps.yx[1] * lon_step
            header_info += '\nlat=%.6f, lon=%.6f' % (lat, lon)
        except:
            pass

        if inps.ref_yx:
            header_info += '\nreference pixel: y=%d, x=%d' % (inps.ref_yx[0], inps.ref_yx[1])
        else:
            header_info += '\nreference pixel: y=%s, x=%s' % (atr['ref_y'], atr['ref_x'])

        header_info += '\nunit=m/yr'
        np.savetxt(outName, zip(np.array(dateList), np.array(d_ts) / inps.unit_fac), fmt='%s', \
                   delimiter='    ', header=header_info)
        print('save time series displacement in meter to ' + outName)


        # Figure - point time series
        outName = inps.fig_base + '_ts.pdf'
        fig_ts.savefig(outName, bbox_inches='tight', transparent=True, dpi=inps.fig_dpi)
        print('save time series plot to ' + outName)

        # Figure - map
        outName = inps.fig_base + '_' + dateList[inps.epoch_num] + '.png'
        fig_v.savefig(outName, bbox_inches='tight', transparent=True, dpi=inps.fig_dpi)
        print('save map plot to ' + outName)



################### PLOT SETUP HELPER FUCNTIONS ###################

def read_timeseries_info():
    global atr, k, h5, dateList, tims, date_num, inps

    atr = readfile.read_attribute(inps.timeseries_file)
    k = atr['FILE_TYPE']
    print('input file is ' + k + ': ' + inps.timeseries_file)

    if not k == 'timeseries':
        raise ValueError('Only timeseries file is supported!')

    h5 = h5py.File(inps.timeseries_file, 'r')
    dateList = sorted(h5[k].keys())
    date_num = len(dateList)
    inps.dates, tims = ptime.date_list2vector(dateList)


def exclude_dates():
    global inps, dateList

    if inps.ex_date_list:
        input_ex_date = list(inps.ex_date_list)
        inps.ex_date_list = []

        if input_ex_date:
            for ex_date in input_ex_date:

                if os.path.isfile(ex_date):
                    ex_date = ptime.read_date_list(ex_date)
                else:
                    ex_date = [ptime.yyyymmdd(ex_date)]

                inps.ex_date_list += list(set(ex_date) - set(inps.ex_date_list))

            # delete dates not existed in input file
            inps.ex_date_list = sorted(list(set(inps.ex_date_list).intersection(dateList)))
            inps.ex_dates = ptime.date_list2vector(inps.ex_date_list)[0]
            inps.ex_idx_list = sorted([dateList.index(i) for i in inps.ex_date_list])
            print('exclude date:' + str(inps.ex_date_list))


def set_zero_displacement():
    global inps, date_num

    if inps.zero_first:
        if inps.ex_date_list:
            inps.zero_idx = min(list(set(range(date_num)) - set(inps.ex_idx_list)))
        else:
            inps.zero_idx = 0


def compute_file_size():
    global atr, width, length

    length = int(atr['FILE_LENGTH'])
    width = int(atr['WIDTH'])
    print('data size in [y0,y1,x0,x1]: [%d, %d, %d, %d]' % (0, length, 0, width))


def compute_lat_lon_params():
    global ullon, ullat, lon_step, lat_step, atr, width, length

    try:
        ullon = float(atr['X_FIRST'])
        ullat = float(atr['Y_FIRST'])
        lon_step = float(atr['X_STEP'])
        lat_step = float(atr['Y_STEP'])
        lrlon = ullon + width * lon_step
        lrlat = ullat + length * lat_step
        print('data size in [lat0,lat1,lon0,lon1]: [%.4f, %.4f, %.4f, %.4f]' % (lrlat, ullat, ullon, lrlon))
    except:
        pass


def set_inital_pixel_coords():
    global inps, atr

    if inps.lalo and 'Y_FIRST' in atr.keys():
        y, x = set_yx_coords(inps.lalo[0], inps.lalo[1])
        inps.yx = [y, x]
    if inps.ref_lalo and 'Y_FIRST' in atr.keys():
        y, x = set_yx_coords(inps.ref_lalo[0], inps.ref_lalo[1])
        inps.ref_yx = [y, x]


def set_yx_coords(y_input, x_input):
    global ullat, ullon, lat_step, lon_step

    y = int((y_input - ullat) / lat_step + 0.5)
    x = int((x_input - ullon) / lon_step + 0.5)

    return y, x


def set_unit_fraction():
    global inps

    if inps.disp_unit == 'cm':
        inps.unit_fac = 100.0
    elif inps.disp_unit == 'm':
        inps.unit_fac = 1.0
    elif inps.disp_unit == 'dm':
        inps.unit_fac = 10.0
    elif inps.disp_unit == 'mm':
        inps.unit_fac = 1000.0
    elif inps.disp_unit == 'km':
        inps.unit_fac = 0.001
    else:
        raise ValueError('Un-recognized unit: ' + inps.disp_unit)
    print('data    unit: m')
    print('display unit: ' + inps.disp_unit)


def flip_map():
    global inps, atr

    if inps.auto_flip:
        inps.flip_lr, inps.flip_ud = view.auto_flip_direction(atr)
    else:
        inps.flip_ud = False
        inps.flip_lr = False


def set_mask():
    global mask, inps, atr

    if not inps.mask_file:
        if os.path.basename(inps.timeseries_file).startswith('geo_'):
            file_list = ['geo_maskTempCoh.h5']
        else:
            file_list = ['maskTempCoh.h5', 'mask.h5']

        try:
            inps.mask_file = ut.get_file_list(file_list)[0]
        except:
            inps.mask_file = None

    try:
        mask = readfile.read(inps.mask_file, epoch='mask')[0]
        mask[mask!=0] = 1
        print('load mask from file: '+inps.mask_file)
    except:
        mask = None
        print('No mask used.')


def set_initial_map():
    global d_v, h5, k, dateList, inps, data_lim

    d_v = h5[k].get(dateList[inps.epoch_num])[:] * inps.unit_fac

    if inps.ref_date:
        inps.ref_d_v = h5[k].get(inps.ref_date)[:] * inps.unit_fac
        d_v -= inps.ref_d_v

    if mask is not None:
        d_v = mask_matrix(d_v, mask)

    if inps.ref_yx:
        d_v -= d_v[inps.ref_yx[0], inps.ref_yx[1]]

    data_lim = [np.nanmin(d_v), np.nanmax(d_v)]

    if not inps.ylim_mat:
        inps.ylim_mat = data_lim
    print('Initial data range: '+str(data_lim))
    print('Display data range: '+str(inps.ylim_mat))

    print('Initial data range: ' + str(data_lim))
    print('Display data range: ' + str(inps.ylim))


def setup_plot():
    # Time Series Info
    read_timeseries_info()
    # Read exclude dates
    exclude_dates()
    # Zero displacement for 1st acquisition
    set_zero_displacement()
    # File Size
    compute_file_size()
    # Latitude Longitude Parameters
    compute_lat_lon_params()
    # Initial Pixel Coordinates
    set_inital_pixel_coords()
    # Display Unit
    set_unit_fraction()
    # Flip up-down / left-right
    flip_map()
    # Mask file
    set_mask()
    # Initial Map
    set_initial_map()



################# PLOT CONFIGURATION HELPER METHODS #######################

def set_dem_file():
    global ax_v, inps, img

    if inps.dem_file:
        dem = readfile.read(inps.dem_file, epoch='height')[0]
        ax_v = view.plot_dem_yx(ax_v, dem)

    img = ax_v.imshow(d_v, cmap=inps.colormap, clim=inps.ylim_mat, interpolation='nearest')


def set_map_reference_pixel():
    global d_v, inps, ax_v, atr

    if inps.ref_yx:
        d_v -= d_v[inps.ref_yx[0], inps.ref_yx[1]]
        ax_v.plot(inps.ref_yx[1], inps.ref_yx[0], 'ks', ms=6)
    else:
        try:
            ax_v.plot(int(atr['ref_x']), int(atr['ref_y']), 'ks', ms=6)
        except:
            pass


def set_plot_axis_params():
    global inps, d_v, ax_v, atr

    if inps.yx:
        ax_v.plot(inps.yx[1], inps.yx[0], 'ro', markeredgecolor='black')

    ax_v.set_xlim(0, np.shape(d_v)[1])
    ax_v.set_ylim(np.shape(d_v)[0], 0)
    ax_v.format_coord = format_coord

    # Title and Axis Label
    ax_v.set_title('N = %d, Time = %s' % (inps.epoch_num, inps.dates[inps.epoch_num].strftime('%Y-%m-%d')))

    if not 'Y_FIRST' in atr.keys():
        ax_v.set_xlabel('Range')
        ax_v.set_ylabel('Azimuth')


def flip_axis():
    global inps, ax_v

    if inps.flip_lr:
        ax_v.invert_xaxis()
        print('flip map left and right')
    if inps.flip_ud:
        ax_v.invert_yaxis()
        print('flip map up and down')


def make_color_bar():
    global fig_v, img, inps
    # Colorbar
    cbar_axes = fig_v.add_axes([0.065, 0.32, 0.40, 0.03])
    cbar = fig_v.colorbar(img, cax=cbar_axes, orientation='horizontal')
    cbar.set_label('Displacement [%s]' % inps.disp_unit)


def make_time_slider():
    global tslider, fig_v, tims, inps

    ax_time = fig_v.add_axes([0.07, 0.10, 0.37, 0.07], axisbg='lightgoldenrodyellow', yticks=[])
    tslider = Slider(ax_time, '', tims[0], tims[-1], valinit=tims[inps.epoch_num])
    tslider.ax.bar(tims, np.ones(len(tims)), facecolor='black', width=0.01, ecolor=None)
    tslider.ax.set_xticks(np.round(np.linspace(tims[0], tims[-1], num=5) * 100) / 100)
    tslider.on_changed(time_slider_update)


def configure_plot():
    # DEM File
    set_dem_file()
    # Reference Pixel
    set_map_reference_pixel()
    # Initial Pixel
    set_plot_axis_params()
    # Flip Axis
    flip_axis()
    # Construct Color Bar
    make_color_bar()
    # Construct Time Slider
    make_time_slider()


################### PLOTTING HELPER FUNCTIONS #######################
def time_slider_update(val):
    '''Update Displacement Map using Slider'''
    global tims, tslider, ax_v, d_v, inps, img, fig_v, h5, k, dateList
    timein = tslider.val
    idx_nearest = np.argmin(np.abs(np.array(tims) - timein))
    ax_v.set_title('N = %d, Time = %s' % (idx_nearest, inps.dates[idx_nearest].strftime('%Y-%m-%d')))
    d_v = h5[k].get(dateList[idx_nearest])[:] * inps.unit_fac
    if inps.ref_date:
        d_v -= inps.ref_d_v
    if mask is not None:
        d_v = mask_matrix(d_v, mask)
    if inps.ref_yx:
        d_v -= d_v[inps.ref_yx[0], inps.ref_yx[1]]
    img.set_data(d_v)
    fig_v.canvas.draw()


def format_coord(x, y):
    global width, length, ullat, lat_step, ullon, lon_step, d_v, lat, lonf

    col = int(x + 0.5)
    row = int(y + 0.5)
    if 0 <= col < width and 0 <= row < length:
        z = d_v[row, col]
        try:
            lon = ullon + x * lon_step
            lat = ullat + y * lat_step
            return 'x=%.0f, y=%.0f, value=%.4f, lon=%.4f, lat=%.4f' % (x, y, z, lon, lat)
        except:
            return 'x=%.0f, y=%.0f, value=%.4f' % (x, y, z)


def plot_timeseries_errorbar(ax, dis_ts, inps):
    global date_num

    dates = list(inps.dates)
    d_ts = dis_ts[:]
    if inps.ex_date_list:
        # Update displacement time-series
        dates = sorted(list(set(inps.dates) - set(inps.ex_dates)))
        ex_d_ts = np.array([dis_ts[i] for i in inps.ex_idx_list])
        d_ts = np.array([dis_ts[i] for i in range(date_num) if i not in inps.ex_idx_list])
        # Plot excluded dates
        (_, caps, _) = ax.errorbar(inps.ex_dates, ex_d_ts, yerr=inps.ex_error_ts, fmt='-o', color='gray', \
                                   ms=inps.marker_size, lw=0, alpha=1, mfc='gray', \
                                   elinewidth=inps.edge_width, ecolor='black', capsize=inps.marker_size * 0.5)
        for cap in caps:  cap.set_markeredgewidth(inps.edge_width)
    # Plot kept dates
    (_, caps, _) = ax.errorbar(dates, d_ts, yerr=inps.error_ts, fmt='-o', \
                               ms=inps.marker_size, lw=0, alpha=1, \
                               elinewidth=inps.edge_width, ecolor='black', capsize=inps.marker_size * 0.5)
    for cap in caps:  cap.set_markeredgewidth(inps.edge_width)
    return ax


def plot_timeseries_scatter(ax, dis_ts, inps, plot_num=1):
    global date_num

    dates = list(inps.dates)
    d_ts = dis_ts[:]
    if inps.ex_date_list:
        # Update displacement time-series
        dates = sorted(list(set(inps.dates) - set(inps.ex_dates)))
        ex_d_ts = np.array([dis_ts[i] for i in inps.ex_idx_list])
        d_ts = np.array([dis_ts[i] for i in range(date_num) if i not in inps.ex_idx_list])
        # Plot excluded dates
        ax.scatter(inps.ex_dates, ex_d_ts, s=inps.marker_size ** 2, color='gray')  # color='crimson'
    # Plot kept dates
    color = 'blue'
    if plot_num == 2:
        color = 'crimson'
    print('Color is ' + color)
    scatter = ax.scatter(dates, d_ts, s=inps.marker_size ** 2, label='1', color=color)

    return ax, scatter


def update_timeseries(y, x, plot_number, data_only=False):
    '''Plot point time series displacement at pixel [y, x]'''
    global fig_ts, ax_ts, second_plot_axis, inps, dateList, h5, k, inps, tims, fig_v, date_num, d_ts

    set_scatter_coords(plot_number, x, y)

    if plot_number == 1:
        axis = ax_ts
    else:
        axis = second_plot_axis

    d_ts = []
    for date in dateList:
        d = h5[k].get(date)[y, x]
        if inps.ref_yx:
            d -= h5[k].get(date)[inps.ref_yx[0], inps.ref_yx[1]]
        d_ts.append(d * inps.unit_fac)

    if inps.zero_first:
        d_ts -= d_ts[inps.zero_idx]

    if data_only:
        return d_ts

    axis.cla()
    if inps.error_file:
        axis = plot_timeseries_errorbar(ax_ts, d_ts, inps)
    else:
        axis, scatter = plot_timeseries_scatter(axis, d_ts, inps, plot_number)
        scatter.set_label('2')

    axis.set_ylim(inps.ylim_mat[0]*2, inps.ylim_mat[1]*2)
    for tick in axis.yaxis.get_major_ticks():
        tick.label.set_fontsize(inps.font_size)

    # Title
    title_ts = set_axis_title(x, y)
    if inps.disp_title:
        axis.set_title(title_ts)

    axis = ptime.auto_adjust_xaxis_date(axis, tims, fontSize=inps.font_size)[0]
    axis.set_xlabel('Time', fontsize=inps.font_size)
    axis.set_ylabel('Displacement [%s]' % inps.disp_unit, fontsize=inps.font_size)

    fig_v.canvas.draw()

    # Print to terminal
    print('\n---------------------------------------')
    print(title_ts)
    print(d_ts)

    # Slope estimation
    estimate_slope()

    return d_ts


def set_axis_title(x, y):
    global lat, lon, ullon, ullat, lat_step, lon_step

    if x is None:
        title_ts = 'No Point Selected'
    else:

        title_ts = 'Y = %d, X = %d' % (y, x)
        try:
            lat, lon = xy_to_lat_lon(x, y)
            title_ts += ', lat = %.4f, lon = %.4f' % (lat, lon)
        except:
            pass

    return title_ts


def xy_to_lat_lon(x, y):
    global ullat, ullon, lat_step, lon_step

    latitude = ullat + y * lat_step
    longitude = ullon + x * lon_step

    return latitude, longitude


def estimate_slope():
    global inps, tims, d_ts, date_num

    if inps.ex_date_list:
        tims_kept = [tims[i] for i in range(date_num) if i not in inps.ex_idx_list]
        d_ts_kept = [d_ts[i] for i in range(date_num) if i not in inps.ex_idx_list]
        d_slope = stats.linregress(np.array(tims_kept), np.array(d_ts_kept))
    else:
        d_slope = stats.linregress(np.array(tims), np.array(d_ts))

    print('linear velocity: %.2f +/- %.2f [%s/yr]' % (d_slope[0], d_slope[4], inps.disp_unit))


def set_scatter_coords(plot_number, x, y):
    global p1_x, p1_y, p2_x, p2_y

    if plot_number == 1:
        p1_x, p1_y = x, y
    else:
        p2_x, p2_y = x, y


def plot_timeseries_event(event):
    '''Event function to get y/x from button press'''
    global ax_v, d_ts, p1_scatter_point, p2_scatter_point, second_plot_axis, p1_x, p1_y, p2_x, p2_y

    if event.inaxes != ax_v:
        return

    ii = int(event.ydata + 0.5)
    jj = int(event.xdata + 0.5)

    if event.button == 1:

        if p1_scatter_point is not None:
            p1_scatter_point.remove()

        p1_scatter_point = ax_v.scatter(event.xdata, event.ydata, s=50, c='red', marker='o')

        d_ts = update_timeseries(ii, jj, 1)

    elif event.button == 3 and second_plot_axis_visible:

        if p2_scatter_point is not None:
            p2_scatter_point.remove()

        p2_scatter_point = ax_v.scatter(event.xdata, event.ydata, s=50, c='blue', marker='o')

        d_ts = update_timeseries(ii, jj, 2)


# Displays second data plot to screen
def show_second_plot(event):

    global fig_v, second_plot_axis, second_plot_axis_visible

    second_plot_axis = fig_v.add_axes([0.55, 0.18, 0.42, 0.3])
    second_plot_axis_visible = True

    fig_v.canvas.draw()


# Hides second data plot from screen
def hide_second_plot(event):
    global second_plot_axis, fig_v, p2_scatter_point, second_plot_axis_visible

    if p2_scatter_point is not None:
        p2_scatter_point.remove()
        p2_scatter_point = None

    second_plot_axis.remove()

    second_plot_axis_visible = False

    fig_v.canvas.draw()


# Displays Scatter Plot Data from one or both data axes in separate figure for anlaysis
def show_data_as_fig(event):
    global second_plot_axis, ax_ts, second_plot_axis_visible

    if ax_ts == event.inaxes or second_plot_axis == event.inaxes:
        show_figure(1)
        if second_plot_axis_visible:
            show_figure(2)


# Configures and Shows Data Plot as Separate Figure Window
def show_figure(plot_number):
    global p2_x, p2_y, p1_x, p1_y, ax_ts, inps, plot_figure, p1_scatter, p2_scatter, new_axes, annot

    plot_figure = plt.figure("PLOT!!", figsize=(10, 5))

    new_axes = plot_figure.add_subplot(111)
    new_axes.set_ylim(inps.ylim_mat[0]*2, inps.ylim_mat[1]*2)

    annot = new_axes.annotate("", xy=(0, 0), xytext=(445, 10), textcoords="axes points", bbox=dict(boxstyle="round", fc="w"))

    annot.set_visible(False)

    d_ts_n = set_timeseries_data(plot_number)

    scatter = plot_timeseries_scatter(new_axes, d_ts_n, inps, plot_number)

    if plot_number == 1:
        _, p1_scatter = scatter
    elif plot_number == 2:
        _, p2_scatter = scatter

    set_title_and_legend(new_axes)

    plot_figure.canvas.mpl_connect('pick_event', hide_scatter)
    plot_figure.canvas.mpl_connect('motion_notify_event', on_hover)

    plot_figure.show()
    plot_figure.canvas.draw()


def on_hover(event):
    global plot_figure, annot, p1_scatter, p2_scatter, new_axes

    vis = annot.get_visible()
    if event.inaxes == new_axes:
        cont, ind = p1_scatter.contains(event)
        if cont:
            update_annot(ind, p1_scatter)
            annot.set_visible(True)
            plot_figure.canvas.draw_idle()
        else:
            cont, ind = p2_scatter.contains(event) if p2_scatter is not None else (False, 0)
            if cont:
                update_annot(ind, p2_scatter)
                annot.set_visible(True)
                plot_figure.canvas.draw_idle()
            else:
                if vis:
                    annot.set_visible(False)
                    plot_figure.canvas.draw_idle()


def update_annot(ind, sc):
    global p1_x, p1_y, p2_x, p2_y, annot, p1_scatter, p2_scatter, tims, lat, lon

    pos = sc.get_offsets()[ind["ind"][0]]
    annot.xy = pos

    if sc is p1_scatter and p1_x is not None:
        data = update_timeseries(p1_y, p1_x, 1, True)
        latitude, longitude = xy_to_lat_lon(p1_x, p1_y)
    elif sc is p2_scatter and p2_x is not None:
        data = update_timeseries(p2_y, p2_x, 2, True)
        latitude, longitude = xy_to_lat_lon(p2_x, p2_y)
    else:
        data = np.zeros(len(tims))
        latitude, longitude = None, None

    raw_date = str(dateList[ind["ind"][0]])
    date = list(raw_date)
    date.insert(4, '-')
    date.insert(7, '-')
    date = "".join(date)
    datum = str(data[ind["ind"][0]])

    text = "(%.4f , %.4f)" % (latitude, longitude)
    text += "\nDate: "+date+"\n"+datum
    annot.set_text(text)
    annot.get_bbox_patch().set_facecolor('b')
    annot.get_bbox_patch().set_alpha(0.4)


# Hides Scatter Plot Data on Data Point Figure on Legend Item Click
def hide_scatter(event):
    global scatts, plot_figure

    legline = event.artist
    origline = scatts[legline]
    vis = not origline.get_visible()
    origline.set_visible(vis)

    # Change the alpha on the line in the legend so we can see what lines
    # have been toggled
    if vis:
        legline.set_alpha(1.0)
    else:
        legline.set_alpha(0.2)

    plot_figure.canvas.draw_idle()


# Sets title and legend information in Data Point Figure
def set_title_and_legend(axis):
    global p1_x, p1_y, p2_x, p2_y, inps, p1_scatter, p2_scatter, scatts

    # Compute title based off lat/lon coords
    series_label_1 = set_axis_title(p1_x, p1_y)
    series_label_2 = None

    title = series_label_1

    if p2_x is not None:
        series_label_2 = set_axis_title(p2_x, p2_y)
        title += " vs " + series_label_2

    # Display title
    if inps.disp_title:
        axis.set_title(title)

    # Set Legend
    legend = axis.legend((p1_scatter, p2_scatter), (series_label_1, series_label_2), fancybox=True)
    legend.get_frame().set_alpha(0.4)
    scatters = [p1_scatter, p2_scatter]
    scatts = dict()

    for legline, scatter in zip(legend.legendHandles, scatters):
        if legline is not None:
            legline.set_picker(5)  # 5 pts tolerance
            scatts[legline] = scatter


def set_timeseries_data(plot_number):
    global tims, p1_y, p1_x, p2_y, p2_x, ax_ts, second_plot_axes

    x_point, y_point = p1_x, p1_y

    if plot_number == 2:
        x_point = p2_x
        y_point = p2_y

    return compute_timeseries_data(plot_number, x_point, y_point)


def compute_timeseries_data(plot_number, x_point, y_point):
    global tims

    if x_point is not None:
        d_ts_n = update_timeseries(y_point, x_point, plot_number)
    else:
        d_ts_n = np.zeros(len(tims))

    return d_ts_n


######################## MAIN FUNCTION ########################
def main(argv):
    global fig_v, ax_v, inps, ax_ts, fig_ts, second_plot_axis

    inps = cmdLineParse(argv)

    setup_plot()

    ########## Main Figure- Cumulative Displacement Map
    if not inps.disp_fig:
        plt.switch_backend('Agg')

    fig_v = plt.figure('Cumulative Displacement', figsize=inps.fig_size)

    ######### Map Axis - Displacement Map Axis
    ax_v = fig_v.add_axes([0.035, 0.42, 0.5, 0.5])

    configure_plot()

    ########## Plot Axes - Time Series Displacement - Points
    ax_ts = fig_v.add_axes([0.55, 0.62, 0.42, 0.3])
    second_plot_axis = fig_v.add_axes([0.55, 0.18, 0.42, 0.3])
    second_plot_axis.remove()

    # Read Error List
    read_error_list()
    # Plot Data from Initial Point on Map
    plot_data_from_inital_point()

    ######### Second Plot Axis Buttons - Show/Hide Axis and Data
    ax_button_show = fig_v.add_axes([0.8, 0.03, 0.18, 0.045])
    show_button = Button(ax_button_show, "Display Second Plot")
    show_button.on_clicked(show_second_plot)

    ax_button_hide = fig_v.add_axes([0.61, 0.03, 0.18, 0.045])
    hide_button = Button(ax_button_hide, "Hide Second Plot")
    hide_button.on_clicked(hide_second_plot)

    ########## Output
    save_output()

    ########## MPL Connection Actions
    first_data_point = fig_v.canvas.mpl_connect('button_press_event', plot_timeseries_event)
    show_data_figure = fig_v.canvas.mpl_connect('button_press_event', show_data_as_fig)

    display_figure()

    ########## MPL Disconnect Actions
    fig_v.canvas.mpl_disconnect(first_data_point)
    fig_v.canvas.mpl_disconnect(show_data_figure)

###########################################################################################
if __name__ == '__main__':
    main(sys.argv[1:])