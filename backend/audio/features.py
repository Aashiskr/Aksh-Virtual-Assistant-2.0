from __future__ import annotations

import math

import numpy as np


def speaker_embedding(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    signal = np.asarray(samples, dtype=np.float32).flatten()
    if signal.size < int(sample_rate * 0.45):
        raise ValueError("Voice sample is too short")
    signal -= signal.mean()
    peak = float(np.max(np.abs(signal)))
    if peak < 100:
        raise ValueError("Voice sample is too quiet")
    signal /= peak

    frame_length = max(256, int(0.025 * sample_rate))
    hop = max(128, int(0.010 * sample_rate))
    frame_count = 1 + max(0, (signal.size - frame_length) // hop)
    if frame_count < 12:
        raise ValueError("Not enough voiced frames")
    frames = np.vstack(
        [
            signal[index * hop : index * hop + frame_length]
            for index in range(frame_count)
        ]
    )
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    keep = rms > max(0.015, float(np.percentile(rms, 35)) * 0.55)
    frames, rms = frames[keep], rms[keep]
    if len(frames) < 10:
        raise ValueError("No clear speech detected")

    preemphasized = np.concatenate(
        [frames[:, :1], frames[:, 1:] - 0.97 * frames[:, :-1]], axis=1
    )
    n_fft = 512
    windowed = preemphasized * np.hamming(frame_length)
    power = (np.abs(np.fft.rfft(windowed, n=n_fft)) ** 2) / n_fft
    filters = _mel_filterbank(sample_rate, n_fft, 26)
    log_mel = np.log(np.maximum(power @ filters.T, 1e-10))
    cosine = np.cos(
        np.pi
        / log_mel.shape[1]
        * (np.arange(log_mel.shape[1]) + 0.5)[:, None]
        * np.arange(13)[None, :]
    )
    mfcc = (log_mel @ cosine)[:, 1:13]
    delta = np.diff(mfcc, axis=0)

    zero_crossing = np.mean(np.abs(np.diff(np.signbit(frames), axis=1)), axis=1)
    spectral = np.abs(np.fft.rfft(frames * np.hamming(frame_length), n=n_fft))
    frequencies = np.fft.rfftfreq(n_fft, 1 / sample_rate)
    spectral_sum = spectral.sum(axis=1) + 1e-9
    centroid = (spectral * frequencies).sum(axis=1) / spectral_sum
    bandwidth = np.sqrt(
        (
            spectral * (frequencies[None, :] - centroid[:, None]) ** 2
        ).sum(axis=1)
        / spectral_sum
    )
    embedding = np.concatenate(
        [
            mfcc.mean(axis=0),
            mfcc.std(axis=0),
            np.percentile(mfcc, 25, axis=0),
            np.percentile(mfcc, 75, axis=0),
            delta.mean(axis=0),
            delta.std(axis=0),
            np.array(
                [
                    rms.mean(),
                    rms.std(),
                    zero_crossing.mean(),
                    zero_crossing.std(),
                    centroid.mean() / sample_rate,
                    centroid.std() / sample_rate,
                    bandwidth.mean() / sample_rate,
                    bandwidth.std() / sample_rate,
                ],
                dtype=np.float32,
            ),
        ]
    ).astype(np.float32)
    embedding -= embedding.mean()
    embedding /= np.linalg.norm(embedding) + 1e-9
    return embedding


def _mel_filterbank(
    sample_rate: int, n_fft: int, filter_count: int
) -> np.ndarray:
    def hz_to_mel(value: float) -> float:
        return 2595.0 * math.log10(1.0 + value / 700.0)

    def mel_to_hz(value: np.ndarray) -> np.ndarray:
        return 700.0 * (10 ** (value / 2595.0) - 1.0)

    points = np.linspace(
        hz_to_mel(80), hz_to_mel(min(7600, sample_rate / 2)), filter_count + 2
    )
    bins = np.floor((n_fft + 1) * mel_to_hz(points) / sample_rate).astype(int)
    bins = np.clip(bins, 0, n_fft // 2)
    bank = np.zeros((filter_count, n_fft // 2 + 1), dtype=np.float32)
    for index in range(1, filter_count + 1):
        left, center, right = bins[index - 1 : index + 2]
        center = center if center != left else center + 1
        right = right if right != center else right + 1
        for position in range(left, min(center, bank.shape[1])):
            bank[index - 1, position] = (position - left) / max(1, center - left)
        for position in range(center, min(right, bank.shape[1])):
            bank[index - 1, position] = (right - position) / max(1, right - center)
    return bank
