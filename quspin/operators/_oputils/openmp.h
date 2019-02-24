#ifndef _OPENMP_H
#define _OPENMP_H

#if defined(_OPENMP)
#include <omp.h>



template<class T>
void inline atomic_add(T &y,const T &aa){
    #pragma omp atomic
    y += aa;
}

template<class T>
void inline atomic_add(std::complex<T> &y,const std::complex<T> &aa){
    T * y_v = reinterpret_cast<T*>(&y);
    const T * aa_v = reinterpret_cast<const T*>(&aa);

    #pragma omp atomic
    y_v[0] += aa_v[0];
    #pragma omp atomic
    y_v[1] += aa_v[1];    
}

#else
typedef int omp_int_t;
inline omp_int_t omp_get_thread_num() { return 0;}
inline omp_int_t omp_get_num_threads() { return 1;}
inline omp_int_t omp_get_max_threads() { return 1;}
#endif

#endif