#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Nov 19 15:20:37 2024

@author: Basile Dupont
"""


import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import random
import math
from scipy.signal import butter, filtfilt, hilbert, decimate
import data_generation.arrival_time

# Generate signal with discrete exponential tails and random radiation in the coda
def generate_diracs(delta_pP, delta_sP, source, station, dt=0.01, duration=60, tau=3.0, plot=False):
    """
    Generates a signal with Diracs for P, pP, and sP, each followed by an exponential tail 
    represented by a series of Diracs, with random sign flips in the coda.
    
    Parameters:
    - delta_pP: delay pP-P in seconds
    - delta_sP: delay sP-P in seconds
    - dt: sampling step (in seconds); 100 Hz
    - duration: total signal duration (in seconds)
    - tau: time constant for exponential decay (in seconds)
    - coda_duration: maximum duration of the tail (in seconds)
    
    Returns:
    - signal: array containing the signal
    - time: array containing the corresponding time instances
    """
    # Compute coda duration from distance between station and epicenter
    P_velocity = 7.5e3 # average P-waves velocity in the crust and upper mantle
    dist_epi = data_generation.arrival_time.direct_distance(source[0], source[1], source[2], station[0], station[1], 0)
    coda_duration = int(dist_epi / P_velocity)
    
    # Discrete time
    time = np.arange(0, duration, dt)
    signal = np.zeros_like(time)
    
    # Function to add an exponential tail as Diracs with controlled sign flips
    def add_coda_diracs(signal, start_index, amplitude, initial_sign):
        dt_factor = 10  # Controls spacing between two diracs ; 0.1s
        sign = initial_sign  # Start with the initial sign
        for i in range(1, int(coda_duration / (dt_factor * dt))):  # Adjust iteration
            index = start_index + i * dt_factor
            if index >= len(signal):  # If exceeding signal duration
                break
                
            # 10% chance to flip the sign
            if random.random() < 0.1:
                sign *= -1  # Flip the sign
                
            # Add the Dirac to the signal
            signal[index] += sign * amplitude * np.exp(-i * dt_factor * dt / tau)
    
    # Amplitude and radiation (random sign) of the P wave
    amplitude_P = random.uniform(0.5, 1.0)  # Amplitude between 0.5 and 1
    sign_P = random.choice([-1, 1])  # Random sign for P to simulate radiation pattern at source
    signal[0] = sign_P * amplitude_P  # Simulate P-wave dirac
    add_coda_diracs(signal, 0, amplitude_P, sign_P)  # Add tail to simulate exponential energy decrease
    
    # Position of first Dirac before tail
    pP_index = int(delta_pP / dt)
    sP_index = int(delta_sP / dt)
    
    # pP
    if pP_index < len(signal):
        amplitude_pP = amplitude_P * random.uniform(0, 1.1)  # Amplitude between 0% and 110% of P
        sign_pP = random.choice([-1, 1])  # Random sign for pP to simulate radiation pattern at source
        signal[pP_index] = sign_pP * amplitude_pP
        add_coda_diracs(signal, pP_index, amplitude_pP, sign_pP) # Add tail to simulate exponential energy decrease
    
    # sP
    if sP_index < len(signal):
        amplitude_sP = amplitude_P * random.uniform(0, 1.1)  # Amplitude between 0% and 110% of P
        sign_sP = random.choice([-1, 1])  # Random sign for sP to simulate radiation pattern at source
        signal[sP_index] = sign_sP * amplitude_sP
        add_coda_diracs(signal, sP_index, amplitude_sP, sign_sP) # Add tail to simulate exponential energy decrease

    if plot is True:
        plt.figure(figsize=(12,5))
        plt.stem(time, signal, basefmt=" ", label="Raw Signal")
        plt.title("Raw Signal")
        plt.xlabel("Time (s)")
        plt.ylabel("Amplitude")
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.show()

    return signal, time


# Convolution of the signal with a wavelet
def generate_ricker_wavelet(f_c=1.65, dt=0.01, length=1.0):
    """
    Generates a Ricker wavelet.
    
    Parameters:
    - f_c: central frequency (Hz) ; center of 0.8-2.5 later filter
    - dt: sampling step (s); 100 Hz
    - length: total duration of the wavelet (s)
    
    Returns:
    - w: array containing the wavelet
    - t: array of corresponding times
    """
    t = np.arange(-length / 2, length / 2, dt)
    w = (1 - 2 * (np.pi * f_c * t)**2) * np.exp(-(np.pi * f_c * t)**2)
    w /= np.sum(np.abs(w)) # Normalize the wavelet to avoid amplification
    
    return w, t


def convolve_signal_with_wavelet(signal, time, plot=False):
    """
    Convolves a discrete signal with a wavelet.
    
    Parameters:
    - signal: input signal
    - wavelet: wavelet for convolution
    
    Returns:
    - signal_convolved: convolved signal
    """
    wavelet, wavelet_time = generate_ricker_wavelet()
    signal_convolved_full = np.convolve(signal, wavelet, mode="full") # Using mode "full" to minimize artifacts
    valid_length = len(signal)
    start_index = (len(signal_convolved_full) - valid_length) // 2
    signal_convolved = signal_convolved_full[start_index:start_index + valid_length]
    
    if plot is True:
        plt.figure(figsize=(12, 6))
        
        # Wavelet
        plt.subplot(2,1,1)
        plt.plot(wavelet_time, wavelet, label="Ricker Wavelet")
        plt.title("Ricker Wavelet")
        plt.xlabel("Time (s)")
        plt.ylabel("Amplitude")
        plt.grid()
        plt.legend()
        
        # Convolved Signal
        plt.subplot(2,1,2)
        plt.plot(time, signal_convolved, label="Convolved Signal")
        plt.title("Signal Convolved with Wavelet")
        plt.xlabel("Time (s)")
        plt.ylabel("Amplitude")
        plt.grid()
        plt.legend()
        
        plt.tight_layout()
        plt.show()
        
    return signal_convolved


# Add gaussian white noise 
def add_white_noise(signal, snr_db=random.uniform(2, 5)):
    """
    Adds Gaussian white noise to a signal based on the specified signal-to-noise ratio (SNR).
    
    Parameters:
    - signal : array containing the original signal
    - snr_db : signal-to-noise ratio in decibels (dB)
    
    Returns:
    - noisy_signal : the signal with added noise
    """
    # Signal power
    signal_power = np.mean(signal**2)
    # Noise power to achieve the desired SNR
    snr_linear = 10**(snr_db / 10)
    noise_power = signal_power / snr_linear
    # Generate the noise
    noise = np.random.normal(0, np.sqrt(noise_power), size=signal.shape)
    # Add noise to the signal
    noisy_signal = signal + noise
    
    return noisy_signal, snr_db


# Bandpass filter
def bandpass_filter(signal, lowcut=0.8, highcut=2.5, fs=100, order=3):
    """
    Applies a Butterworth bandpass filter.
    
    Parameters:
    - signal : array containing the signal
    - lowcut : lower cutoff frequency (Hz)
    - highcut : upper cutoff frequency (Hz)
    - fs : sampling frequency (Hz)
    - order : filter order (default is 4)
    
    Returns:
    - filtered_signal : filtered signal
    """
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')  # Filter coefficients
    filtered_signal = filtfilt(b, a, signal)  # Apply the filter

    # Z-score normalization
    filtered_signal_normalized = (filtered_signal - np.mean(filtered_signal)) / np.std(filtered_signal)
    
    return filtered_signal_normalized

# Hilbert envelope extraction
def extract_hilbert_envelope(signal):
    """
    Extracts the analytic envelope of a signal using the Hilbert transform.
    
    Parameters:
    - signal : array containing the signal
    
    Returns:
    - envelope : analytic envelope of the signal
    """
    analytic_signal = hilbert(signal)  # Analytic signal
    envelope = np.abs(analytic_signal)  # Envelope (magnitude of the analytic signal)
    envelope /= np.max(envelope)  # Normalize to 1
    
    return envelope



# Generate signal from delta_pP and delta_sP
def generate_one_signal(plot=False, depth=None, use_TauP=True):
    # Generate arrival times
    deltas, source, stations = data_generation.arrival_time.generate_arrival_samples(num_stations=1, depth=depth, use_TauP=use_TauP)
    delta_pP, delta_sP = deltas[0][0], deltas[0][1]
    
    # Generate diracs
    diracs, time = generate_diracs(delta_pP, delta_sP, source, stations[0])

    # Generate signal
    signal = convolve_signal_with_wavelet(diracs, time)

    # Add noise
    noisy_signal, snr_db = add_white_noise(signal)

    # Filter signal
    filtered_signal = bandpass_filter(noisy_signal)

    # Get Hilbert enveloppe
    envelope = extract_hilbert_envelope(filtered_signal)

    # Decimate the envelope to 20 Hz
    envelope = decimate(envelope, q=5, zero_phase=True)

    if plot is True:
        sns.set_style("whitegrid")  # Set style
        sns.set_palette("deep")  # Use a Seaborn color palette
        
        fig, axes = plt.subplots(5, 1, figsize=(15, 8), constrained_layout=True)
        
        # Subplot 1: Diracs
        axes[0].stem(time, diracs, markerfmt=' ', basefmt=' ', linefmt=sns.color_palette()[0])
        axes[0].vlines(delta_pP, min(diracs), max(diracs), color=sns.color_palette()[1])
        axes[0].vlines(delta_sP, min(diracs), max(diracs), color=sns.color_palette()[1])
        axes[0].axhline(0, color='gray', linewidth=0.5)
        axes[0].set_title("Diracs")
        axes[0].set_ylabel("Amplitude")
        axes[0].set_yticks([])  # Hide y-axis ticks
        
        # Subplot 2: Signal
        sns.lineplot(ax=axes[1], x=time, y=signal)
        axes[1].vlines(delta_pP, min(signal), max(signal), color=sns.color_palette()[1])
        axes[1].vlines(delta_sP, min(signal), max(signal), color=sns.color_palette()[1])
        axes[1].axhline(0, color='gray', linewidth=0.5)
        axes[1].set_title("Signal")
        axes[1].set_ylabel("Amplitude")
        axes[1].set_yticks([])  # Hide y-axis ticks
        
        # Subplot 3: Noisy Signal
        sns.lineplot(ax=axes[2], x=time, y=noisy_signal)
        axes[2].vlines(delta_pP, min(noisy_signal), max(noisy_signal), color=sns.color_palette()[1])
        axes[2].vlines(delta_sP, min(noisy_signal), max(noisy_signal), color=sns.color_palette()[1])
        axes[2].axhline(0, color='gray', linewidth=0.5)
        axes[2].set_title(f"Noisy signal (SNR = {snr_db:.1f} dB)")
        axes[2].set_ylabel("Amplitude")
        axes[2].set_yticks([])  # Hide y-axis ticks
        
        # Subplot 4: Filtered Signal
        sns.lineplot(ax=axes[3], x=time, y=filtered_signal)
        axes[3].vlines(delta_pP, min(filtered_signal), max(filtered_signal), color=sns.color_palette()[1])
        axes[3].vlines(delta_sP, min(filtered_signal), max(filtered_signal), color=sns.color_palette()[1])
        axes[3].axhline(0, color='gray', linewidth=0.5)
        axes[3].set_title("Filtered signal")
        axes[3].set_ylabel("Amplitude")
        axes[3].set_yticks([])  # Hide y-axis ticks
        
        # Subplot 5: Normalized Hilbert Envelope
        time_envelope = np.arange(0, 60, 1/20)
        sns.lineplot(ax=axes[4], x=time_envelope, y=envelope)
        axes[4].vlines(delta_pP, min(envelope), max(envelope), color=sns.color_palette()[1])
        axes[4].vlines(delta_sP, min(envelope), max(envelope), color=sns.color_palette()[1])
        axes[4].axhline(0, color='gray', linewidth=0.5)
        axes[4].set_title("Normalized Hilbert envelope")
        axes[4].set_xlabel("Time (s)")
        axes[4].set_ylabel("Amplitude")
        axes[4].set_yticks([])  # Hide y-axis ticks
        
        # Show plot
        plt.show()
        
    return envelope, source, stations



# Reorganise stations based on the distance to the source
def reorganise_distance(deltas, source, stations):
    """
    Reorganize stations and deltas based on their distance to the epicenter.

    Parameters:
        source (tuple): The source coordinates (lat, long, depth).
        stations (list): A list of station coordinates (lat, long).
        deltas (list): A list of delta values corresponding to each station.

    Returns:
        tuple: Reorganized stations and deltas sorted by distance from the source.
    """
    reorg_data = [
        (data_generation.arrival_time.direct_distance(source[0], source[1], 0, station[0], station[1], 0), station, delta)
        for station, delta in zip(stations, deltas)
    ]
    # Sort by distance
    reorg_data.sort(key=lambda x: x[0])

    # Extract sorted stations, distances and deltas
    sorted_stations = [item[1] for item in reorg_data]
    sorted_distances = [item[0] for item in reorg_data]
    sorted_deltas = [item[2] for item in reorg_data]

    return sorted_deltas, sorted_stations, sorted_distances

    
    
# Generate signal from delta_pP and delta_sP for multiple stations
def generate_signals(num_stations=50, depth=None, rand_inactive=0, use_TauP=True):
    """
    Generate signals for multiple stations given a single source.
    
    Parameters:
    - num_stations : number of stations to simulate (default is 50)
    - depth : depth to simulate (default is None)
    - rand_inactive : max number of inactive stations
    - use_TauP : whether to use or not TauP model for propagation
    
    Returns:
    - results : list of tuples (envelope, source, station) for each station
    """
    # Generate arrival times for multiple stations
    deltas, source, stations = data_generation.arrival_time.generate_arrival_samples(num_stations=num_stations, depth=depth, use_TauP=use_TauP)

    # Reorganize deltas and stations from distance to source
    deltas, stations, distances = reorganise_distance(deltas, source, stations)

    # Randomly determine the number of active stations (from 20 to num_stations)
    active_stations = num_stations - random.randint(0, rand_inactive)

    # Generate signals
    results = []
    
    for i, (delta_pP, delta_sP) in enumerate(deltas):
        if i < active_stations:
            # Generate diracs
            diracs, time = generate_diracs(delta_pP, delta_sP, source, stations[i])
            
            # Generate signal
            signal = convolve_signal_with_wavelet(diracs, time)
            
            # Add noise
            noisy_signal, snr_db = add_white_noise(signal)
            
            # Filter signal
            filtered_signal = bandpass_filter(noisy_signal)
            
            # Get Hilbert envelope
            envelope = extract_hilbert_envelope(filtered_signal)
    
            # Decimate the envelope to 20 Hz
            envelope = decimate(envelope, q=5, zero_phase=True)
            
            # Append results for this station
            results.append((envelope, source, stations[i]))

        else:
            # Add zero signals for inactive stations, with no data on source and station
            results.append((np.zeros(1200), [0,0,0], [0,0]))  # 1200 points for 60s at 20 Hz
    
    return results, distances

