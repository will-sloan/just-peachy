import easygui
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, RadioButtons
from scipy.interpolate import pchip_interpolate

class EQ:
    def __init__(self):
        # create plots
        fig, ax = plt.subplots()
        fig.subplots_adjust(bottom=0.3)
        self.axi = fig.add_axes([0.7, 0.05, 0.1, 0.075])
        self.Bimport = Button(self.axi, 'Import')
        self.axb = fig.add_axes([0.81, 0.05, 0.1, 0.075])
        self.Bexport = Button(self.axb, 'Export')
        self.axr = fig.add_axes([0.55, 0.05, 0.1, 0.075])
        self.Breset = Button(self.axr, 'Reset')
        self.axo = fig.add_axes([0.10, 0.05, 0.3, 0.075])
        self.Boctave = RadioButtons(self.axo, ['octave bands', '1/3 octave bands'], active=0)
        self.Boctave.on_clicked(self.select_bands)
        self.axf = fig.add_axes([0.10, 0.13, 0.3, 0.075])
        self.Bfreqrange = RadioButtons(self.axf, ['Wideband', 'Superwideband'], active=0)
        self.Bfreqrange.on_clicked(self.select_fsamp)
        self.Fsamp = 16000
        self.freqrange = 3 * np.log10(self.Fsamp/2000)/np.log10(2) + 1
        self.BeClearrange = 40

        # create UI bins and gains (octave resolution)
        self.fc_oct = self.fc_oct = 10**3 * (2**(np.arange(-12,self.freqrange,3)/3))
        self.k_oct = np.zeros_like(self.fc_oct)

        # create BeClear bins and gains
        self.bin_z = np.arange(0, self.BeClearrange, 1)
        self.fc_z = np.zeros_like(self.bin_z)
        for c1, b in enumerate(self.bin_z):
            self.fc_z[c1] = self.bin_to_freq(b, 512, 16000.0)
        self.k_z = np.zeros_like(self.bin_z)

        # plot BeClear and ui line
        l2d_z, = ax.plot(self.fc_z, self.k_z, marker=".", linestyle='none', markersize=2)
        l2d_oct, = ax.plot(self.fc_oct, self.k_oct, marker="o")

        # layout plot
        ax.set_xscale('log')
        ax.set_ylim(-6.0, 6.0)
        ax.set_xlim(20., 17000.)
        ax.grid()
        ax.set_xticks([50, 100, 200, 500, 1000, 2000, 5000, 10000])
        ax.set_xticklabels(["50", "100", "200", "500", "1000", "2000", "5000", "10k"])
        ax.set_ylabel('Gain (dB)')
        ax.set_xlabel('Frequency (Hz)')
        ax.set_title('Click to adjust EQ')
        ax.legend(['BeClear', 'UI'])

        # store line plots as member vars
        self.line_plot_oct = l2d_oct
        self.line_plot_z = l2d_z

        # register event handler
        self.cid = l2d_z.figure.canvas.mpl_connect('button_press_event', self)


    def __call__(self, event):
        if event.inaxes == self.axr:
            self.reset_eq()
        if event.inaxes == self.axb:
            self.save()
        if event.inaxes == self.axi:
            self.load()
        if event.inaxes == self.line_plot_z.axes:
            self.update_eq(event.xdata, event.ydata)

    def select_bands( self, event):
        fc_old = np.array(self.fc_oct)
        k_old = np.array(self.k_oct)
        if event == 'octave bands':
            self.fc_oct = 10**3 * (2**(np.arange(-12,self.freqrange,3)/3))
        elif event == '1/3 octave bands':
            self.fc_oct = 10**3 * (2**(np.arange(-12,self.freqrange,1)/3))
        self.k_oct = np.clip(pchip_interpolate(fc_old, k_old, self.fc_oct),-6,6)

        self.bin_z = np.arange(0, self.BeClearrange, 1)
        self.fc_z = np.zeros_like(self.bin_z)
        for c1, b in enumerate(self.bin_z):
            self.fc_z[c1] = self.bin_to_freq(b, 512, 16000.0)
        self.k_z = np.zeros_like(self.bin_z)
        self.drawnow()

    def select_fsamp( self, event):
        if event == 'Wideband':
            self.Fsamp = 16000
            self.BeClearrange = 40
        elif event == 'Superwideband':
            self.Fsamp = 32000
            self.BeClearrange = 56
        self.freqrange = 3 * np.log10(self.Fsamp/2000)/np.log10(2) + 1
        self.select_bands( self.Boctave.value_selected )

    def drawnow(self):
        self.line_plot_oct.set_data(self.fc_oct, self.k_oct)
        self.interpolate()
        self.line_plot_oct.figure.canvas.draw()

    def reset_eq(self):
        self.k_oct.fill(0)
        self.interpolate()
        self.drawnow()

    def update_eq(self, x, y):
        x = np.argmin(np.abs(self.fc_oct - x))
        if self.fc_oct[x] in self.fc_oct:
            self.k_oct[x] = y
            self.drawnow()

    def interpolate(self):
        self.k_z = np.clip(pchip_interpolate(self.fc_oct, self.k_oct, self.fc_z), -6, 6 )
        self.line_plot_z.set_data(self.fc_z, self.k_z)

    @staticmethod
    def bin_to_freq(b, M, fs):
        if b < 40:
            M_shift = M >> 8
            B1 = 4 * M_shift
            B2 = 8 * M_shift
            B3 = 32 * M_shift
            B4 = 64 * M_shift
            if b < B1:
                bn = b
            elif b < (B1 + (B2 - B1) / 2):
                bn = 2 * (b - B1) + B1
            elif b < (B1 + (B2 - B1) / 2 + (B3 - B2) / 4):
                bn = (b - B1 - (B2 - B1) / 2) * 4 + B2
            elif b < (B1 + (B2 - B1) / 2 + (B3 - B2) / 4 + (B4 - B3) / 8):
                bn = (b - B1 - (B2 - B1) / 2 - (B3 - B2) / 4) * 8 + B3
            else:
                bn = (b - B1 - (B2 - B1) / 2 - (B3 - B2) / 4 - (B4 - B3) / 8) * 16 + B4
            return bn * fs / M
        else:
            return 8000 + 16 * (b - 40) * fs / M

    @staticmethod
    def db_field(x, ref=1):
        return (20. * np.log10(np.abs(x) / ref) + 300.0) - 300.0

    @staticmethod
    def inv_db_field(y, ref=1):
        return ref * 10. ** (y / 20.)

    def save(self):
        filename = easygui.filesavebox(title='Export eq values to binary file', default='*', filetypes=["*.dat"])
        if filename is None:
            return

        # open file
        fid = open(filename, 'wb')

        # convert decibels to gains and write data as 32bit float
        k = self.inv_db_field(self.k_z)
        fid.write(k.astype(np.float32).tobytes(order='F'))

        # close file
        fid.close()

    def load(self):
        filename = easygui.fileopenbox(title='Import eq values from binary file', default='*', filetypes=["*.dat"])
        if filename is None:
            return

        # Always import at 1/3 octave band frequency
        self.Boctave.set_active(1)

        # open file
        fid = open(filename, 'rb')

        # load data
        k = np.frombuffer(fid.read(), dtype=np.float32)

        # Determine whether data is WB or SWB.
        if k.shape[0] == 40:
            self.Bfreqrange.set_active(0)
        elif k.shape[0] == 56:
            self.Bfreqrange.set_active(1)
        else:
            raise ValueError('EQ coefficient file must have 40 or 56 single precision float values.')

        # convert gains to decibels
        self.k_z = self.db_field(k)
        # close file
        fid.close()

        # update data
        self.k_oct = pchip_interpolate(self.fc_z, self.k_z, self.fc_oct)
        self.line_plot_oct.set_data(self.fc_oct, self.k_oct)
        self.line_plot_z.set_data(self.fc_z, self.k_z)
        self.line_plot_oct.figure.canvas.draw()


if __name__ == '__main__':
    EQ()
    plt.show()
