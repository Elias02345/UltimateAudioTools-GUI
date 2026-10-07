import { describe, expect, it } from 'vitest';
import { validate, bytes, time, activeJob } from '../apps/desktop/src/api';
import type { Preset, Job } from '../apps/desktop/src/api';

const parameters = { device: 'auto', gpu_index: 0, precision: 'float32', overlap: null, segment_size: null, batch_size: 1, mdx_overlap: 0.25, mdx_segment_size: 256, denoise: false, vr_aggression: 5, vr_tta: false, demucs_shifts: 2, torch_compile: false, chunk_duration: null };
const output = { directory: '', format: 'FLAC', sample_rate: 0, bitrate: 320, normalization: 0.98, template: '{original} - {stem}', subfolder: true, collision: 'unique' };
const preset = { version: 1, id: 'test', name: 'Test', description: '', task: 'Both', models: ['model.ckpt'], algorithm: 'avg_fft', weights: null, engine: 'native', parameters, output, builtin: false, quality: 'Custom' };

describe('generated engine contract', () => {
  it('validates complete portable presets', () => { expect(validate<Preset>('Preset', preset).models).toEqual(['model.ckpt']); });
  it('rejects unsupported precision and malformed version', () => { expect(() => validate('Preset', { ...preset, parameters: { ...parameters, precision: 'garbage' } })).toThrow(); expect(() => validate('Preset', { ...preset, version: 2 })).toThrow(); });
  it('rejects unknown fields rather than silently ignoring imports', () => { expect(() => validate('Preset', { ...preset, shell_command: 'bad' })).toThrow(); });
  it('formats real metadata without invented sizes', () => { expect(bytes(null)).toBe('Size unknown'); expect(time(94)).toBe('1:34'); });
  it('distinguishes jobs that really consume resources', () => { expect(activeJob({ status: 'Processing' } as Job)).toBe(true); expect(activeJob({ status: 'Pending' } as Job)).toBe(false); expect(activeJob({ status: 'Interrupted' } as Job)).toBe(false); });
});
