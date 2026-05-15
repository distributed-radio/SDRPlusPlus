/* cuFFT backend — drop-in for the single fftwf_execute call in
 * IQFrontEnd::handler. Build with -DOPT_BUILD_CUFFT_BACKEND=ON.
 *
 * Layout-compatible with fftwf_complex on the host side (both are
 * `float[2]` interleaved IQ), so existing volk routines keep working
 * on `fftInBuf` / `fftOutBuf` unmodified. The cuFFT execution buffers
 * are device-side; we use pinned host memory + cudaMemcpyAsync for
 * the round-trip. */
#pragma once

#ifdef SDRPP_USE_CUFFT
#include <cufft.h>
#include <cuda_runtime.h>

struct CuFFTState {
    cufftHandle    plan;
    cufftComplex*  d_in;
    cufftComplex*  d_out;
    cudaStream_t   stream;
    int            size;
};

void cufft_init(CuFFTState& s, int fftSize);
void cufft_free(CuFFTState& s);
/* Forward C2C; host_in and host_out are pinned (cudaHostAlloc) buffers. */
void cufft_execute_host(CuFFTState& s, void* host_in, void* host_out);

#endif // SDRPP_USE_CUFFT
