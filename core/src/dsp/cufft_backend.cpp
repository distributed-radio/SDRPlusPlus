#include "cufft_backend.h"

#ifdef SDRPP_USE_CUFFT
#include <utils/flog.h>
#include <stdexcept>

void cufft_init(CuFFTState& s, int fftSize) {
    s.size = fftSize;
    if (cudaStreamCreate(&s.stream) != cudaSuccess) {
        throw std::runtime_error("cuFFT: cudaStreamCreate failed");
    }
    if (cudaMalloc(&s.d_in,  fftSize * sizeof(cufftComplex)) != cudaSuccess ||
        cudaMalloc(&s.d_out, fftSize * sizeof(cufftComplex)) != cudaSuccess) {
        throw std::runtime_error("cuFFT: cudaMalloc failed");
    }
    if (cufftPlan1d(&s.plan, fftSize, CUFFT_C2C, 1) != CUFFT_SUCCESS) {
        throw std::runtime_error("cuFFT: cufftPlan1d failed");
    }
    cufftSetStream(s.plan, s.stream);
    flog::info("cuFFT backend initialised, size={}", fftSize);
}

void cufft_free(CuFFTState& s) {
    if (s.plan) { cufftDestroy(s.plan); s.plan = 0; }
    if (s.d_in)  { cudaFree(s.d_in);  s.d_in  = nullptr; }
    if (s.d_out) { cudaFree(s.d_out); s.d_out = nullptr; }
    if (s.stream) { cudaStreamDestroy(s.stream); s.stream = nullptr; }
}

void cufft_execute_host(CuFFTState& s, void* host_in, void* host_out) {
    const size_t bytes = s.size * sizeof(cufftComplex);
    cudaMemcpyAsync(s.d_in, host_in, bytes, cudaMemcpyHostToDevice, s.stream);
    cufftExecC2C(s.plan, s.d_in, s.d_out, CUFFT_FORWARD);
    cudaMemcpyAsync(host_out, s.d_out, bytes, cudaMemcpyDeviceToHost, s.stream);
    cudaStreamSynchronize(s.stream);
}
#endif // SDRPP_USE_CUFFT
