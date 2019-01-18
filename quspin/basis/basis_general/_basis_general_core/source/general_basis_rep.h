#ifndef _GENERAL_BASIS_REP_H
#define _GENERAL_BASIS_REP_H

#include <complex>
#include <limits>
#include "general_basis_core.h"
#include "numpy/ndarraytypes.h"


template<class I,class J>
void general_normalization(general_basis_core<I> *B,
								  I s[],
								  J n[],
							const npy_intp Ns
				)
{	
	for(npy_intp i=0;i<Ns;i++){

		double norm = B->check_state(s[i]);
		J int_norm = norm;

		#if defined(_WIN64)
			// x64 version
			bool isnan = _isnanf(norm) != 0;
		#elif defined(_WIN32)
			bool isnan = _isnan(norm) != 0;
		#else
			bool isnan = std::isnan(norm);
		#endif
		
		if(!isnan && int_norm>0 ){
			n[i] = norm;
		}
		else{
			n[i] = 0;
		}
	}
}


template<class I>
void general_representative(general_basis_core<I> *B,
							const I s[],
									I r[],
									int *g_out_ptr,
									npy_int8 *sign_out_ptr,
							const npy_intp Ns,
							const int nt
						  )
{	int g[128],gg[128];
	int sign;

	if(g_out_ptr && sign_out_ptr){
		for(npy_intp i=0;i<Ns;i++){

			int temp_sign = 1;
			r[i] = B->ref_state(s[i],&g_out_ptr[i*nt],gg,temp_sign);
			sign_out_ptr[i] = temp_sign;
		}
	}
	else if(g_out_ptr){
		for(npy_intp i=0;i<Ns;i++){

			sign = 1;
			r[i] = B->ref_state(s[i],&g_out_ptr[i*nt],gg,sign);
		}
	}
	else if(sign_out_ptr){
		for(npy_intp i=0;i<Ns;i++){

			int temp_sign = 1;
			r[i] = B->ref_state(s[i],g,gg,temp_sign);
			sign_out_ptr[i] = temp_sign;
		}
	}
	else{
		for(npy_intp i=0;i<Ns;i++){

			sign = 1;
			r[i] = B->ref_state(s[i],g,gg,sign);
		}
	}

	

}



#endif
