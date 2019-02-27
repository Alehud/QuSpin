#ifndef _MAKE_GENERAL_BASIS_H
#define _MAKE_GENERAL_BASIS_H

#include <iostream>
#include "general_basis_core.h"
#include "numpy/ndarraytypes.h"
#include "openmp.h"
#include "misc.h"
#include <cmath>
#include <cfloat>
#include <vector>
#include <utility>
#include <algorithm>
#include <functional>



namespace basis_general {

template<class I,class J>
npy_intp make_basis_sequential(general_basis_core<I> *B,npy_intp MAX,npy_intp mem_MAX,I basis[],J n[]){
	npy_intp Ns = 0;
	I s = 0;
	bool insuff_mem = false;

	while(MAX != 0){
		if(Ns>=mem_MAX){
			insuff_mem = true;
			break;
		}
		double norm = B->check_state(s);
		npy_intp int_norm = norm;
		
		if(!check_nan(norm) && int_norm>0 ){
			basis[Ns] = s;
			n[Ns] = norm;
			Ns++;
		}
		s++;
		MAX--;
	}

	if(insuff_mem){
		return -1;
	}
	else{
		return Ns;
	}
}


template<class I,class J>
npy_intp make_basis_pcon_sequential(general_basis_core<I> *B,npy_intp MAX,npy_intp mem_MAX,I s,I basis[],J n[]){
	npy_intp Ns = 0;
	bool insuff_mem = false;

	while(MAX!=0){
		if(Ns>=mem_MAX){
			insuff_mem = true;
			break;
		}
		double norm = B->check_state(s);
		npy_intp int_norm = norm;

		if(!check_nan(norm) && int_norm>0 ){
			basis[Ns] = s;
			n[Ns] = norm;
			Ns++;
		}
		s = B->next_state_pcon(s);
		MAX--;
	}

	if(insuff_mem){
		return -1;
	}
	else{
		return Ns;
	}
}






template<class I, class J>
struct compare_pair : std::binary_function<std::pair<I,J>,std::pair<I,J>,bool>
{
	bool operator()(std::pair<I,J> a, std::pair<I,J> b){return a.first < b.first;}
};



template<class I,class J>
npy_intp make_basis_parallel(general_basis_core<I> *B,const npy_intp MAX,const npy_intp mem_MAX,I basis[],J n[]){
	npy_intp Ns = 0;

	bool insuff_mem = false;
	std::vector<std::pair<I,J> > master_block(mem_MAX);
	std::vector<npy_intp> master_pos(omp_get_max_threads()+1);
	std::pair<I,J> * master_block_data = &master_block[0];
	npy_intp * master_pos_data = &master_pos[0];


	#pragma omp parallel firstprivate(MAX) shared(master_block_data,master_pos_data,Ns,insuff_mem)
	{
		const int nthread = omp_get_num_threads();
		const int threadn = omp_get_thread_num();
		std::vector<std::pair<I,J> > thread_block(0);
		const npy_intp block_size = 1.1*mem_MAX/nthread;
		thread_block.reserve(block_size);

		npy_intp chunk = MAX - threadn;

		I s = threadn;

		while(chunk>0 && !insuff_mem){
			double norm = B->check_state(s);
			npy_intp int_norm = norm;

			if(!check_nan(norm) && int_norm>0 ){
				thread_block.push_back(std::make_pair(s,int_norm));
				#pragma omp atomic
				Ns++;
			}
			s += nthread;
			chunk-=nthread;

			if(Ns>=mem_MAX){
				#pragma omp critical
				insuff_mem=true;
			}

		}



		if(!insuff_mem){

			master_pos_data[threadn+1] = thread_block.size(); // get sizes for each thread block into shared memory

			#pragma omp barrier // wait for all threads to finish searching.

			#pragma omp single // calculate the cumulative sum to get data paritions of master_block
			{
				for(int i=0;i<nthread;i++){
					master_pos_data[i+1] += master_pos_data[i];
				}
			}

			// load data into master block in parallel
			const npy_intp start = master_pos_data[threadn];
			const npy_intp end = master_pos_data[threadn+1];
			npy_intp i = 0;

			for(npy_intp j=start;j<end;j++){
				master_block_data[j] = thread_block[i++];
			}

			#pragma omp barrier

			#pragma omp single
			{
				std::sort(master_block_data, master_block_data + Ns, compare_pair<I,J>());
			}

			#pragma omp for schedule(static)
			for(npy_intp i=0;i<Ns;i++){
				basis[i] = master_block_data[i].first;
				n[i] = master_block_data[i].second;
			}
		}
	}

	if(insuff_mem){
		return -1;
	}
	else{
		// master_block.resize(Ns);
		// std::sort(master_block.begin(),master_block.end(), compare_pair<I,J>());
		// for(npy_intp i=0;i<Ns;i++){
		// 	basis[i] = master_block[i].first;
		// 	n[i] = master_block[i].second;
		// }
		return Ns;
	}
}

template<class I,class J>
npy_intp make_basis_pcon_parallel(general_basis_core<I> *B,const npy_intp MAX,const npy_intp mem_MAX,I s,I basis[],J n[]){
	npy_intp Ns = 0;

	bool insuff_mem = false;
	std::vector<std::pair<I,J> > master_block(mem_MAX);
	std::vector<npy_intp> master_pos(omp_get_max_threads()+1);
	std::pair<I,J> * master_block_data = &master_block[0];
	npy_intp * master_pos_data = &master_pos[0];


	#pragma omp parallel firstprivate(MAX,s) shared(master_block_data,master_pos_data,Ns,insuff_mem)
	{
		
		const int nthread = omp_get_num_threads();
		const int threadn = omp_get_thread_num();
		std::vector<std::pair<I,J> > thread_block(0); // local array to store values found by each thread. this reduces the number of critical sections. 
		const npy_intp block_size = 1.1*mem_MAX/nthread;
		thread_block.reserve(block_size); // preallocate memory for each block so that it does not have to expand during search. 
		
		npy_intp chunk = MAX - threadn;
		for(int i=0;i<threadn;i++){s=B->next_state_pcon(s);}

		while(chunk>0 && !insuff_mem){
			double norm = B->check_state(s);
			npy_intp int_norm = norm;

			if(!check_nan(norm) && int_norm>0 ){
				thread_block.push_back(std::make_pair(s,int_norm));
				#pragma omp atomic
				Ns++;
			}

			for(int i=0;i<nthread;i++){s=B->next_state_pcon(s);}
			chunk-=nthread;

			if(Ns>=mem_MAX){
				#pragma omp critical
				insuff_mem=true;
			}
		}

		if(!insuff_mem){
			master_pos_data[threadn+1] = thread_block.size();

			#pragma omp barrier

			#pragma omp single
			{
				for(int i=0;i<nthread;i++){
					master_pos_data[i+1] += master_pos_data[i];
				}
			}

			const npy_intp start = master_pos_data[threadn];
			const npy_intp end = master_pos_data[threadn+1];
			npy_intp i = 0;

			for(npy_intp j=start;j<end;j++){
				master_block_data[j] = thread_block[i++];
			}

			#pragma omp barrier

			#pragma omp single
			{
				std::sort(master_block_data, master_block_data + Ns, compare_pair<I,J>());
			}

			#pragma omp for schedule(static)
			for(npy_intp i=0;i<Ns;i++){
				basis[i] = master_block_data[i].first;
				n[i] = master_block_data[i].second;
			}
		}
	}

	if(insuff_mem){
		return -1;
	}
	else{
		// sort list based on basis and then fill ndarray values with the sorted list. 
		// master_block.resize(Ns);
		// std::sort(master_block.begin(),master_block.end(), compare_pair<I,J>());
		// for(npy_intp i=0;i<Ns;i++){
		// 	basis[i] = master_block[i].first;
		// 	n[i] = master_block[i].second;
		// }
		return Ns;
	}
}




template<class I,class J>
npy_intp make_basis(general_basis_core<I> *B,npy_intp MAX,npy_intp mem_MAX,I basis[],J n[]){
	const int nt =  B->get_nt();
	const int nthreads = omp_get_max_threads();

	if(nthreads>1 && MAX > nthreads && nt>0){
		return make_basis_parallel(B,MAX,mem_MAX,basis,n);
	}
	else{
		return make_basis_sequential(B,MAX,mem_MAX,basis,n);
	}
}

template<class I,class J>
npy_intp make_basis_pcon(general_basis_core<I> *B,npy_intp MAX,npy_intp mem_MAX,I s,I basis[],J n[]){
	const int nt =  B->get_nt();
	const int nthreads = omp_get_max_threads();

	if(nthreads>1 && MAX > nthreads && nt>0){
		return make_basis_pcon_parallel(B,MAX,mem_MAX,s,basis,n);
	}
	else{
		return make_basis_pcon_sequential(B,MAX,mem_MAX,s,basis,n);
	}
}



template<class I,class J>
npy_intp inline make_basis_wrapper(void *B,npy_intp MAX,npy_intp mem_MAX,void * basis,J n[]){
	return make_basis(reinterpret_cast<general_basis_core<I> *>(B),MAX,mem_MAX,(I*)basis,n);
}

template<class I,class J>
npy_intp inline make_basis_pcon_wrapper(void *B,npy_intp MAX,npy_intp mem_MAX,npy_uint64 s,void * basis,J n[]){
	return make_basis_pcon(reinterpret_cast<general_basis_core<I> *>(B),MAX,mem_MAX,(I)s,(I*)basis,n);
}

}

#endif
