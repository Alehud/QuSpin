from ._basis_general_core import nlce_core_wrap
from ._perm_checks import process_map
import numpy as _np
from numba import njit
from builtins import range


@njit
def _get_W(O,W,data,indices,indptr):
	nrow = O.shape[0]
	nvec = O.shape[1]
	w = O[0,:].copy()
	for i in range(nrow):
		w[:] = O[i,:]
		for k in range(indptr[i],indptr[i+1],1):
			j = indices[k]
			for l in range(nvec):
				w[l] += data[k]*W[j,l]

		W[i,:] = w

@njit
def _get_Sn(W,L,N):
	Ncl = N[-1]

	Nsum = W.shape[0]
	Nobs = W.shape[1]

	Sn = W[:Ncl,:].copy()
	Sn[:,:] = 0
	for i in range(Nsum):
		n = N[i]-1
		l = L[i]
		for j in range(Nobs):
			Sn[n,j] += W[i,j]*l

	return Sn




class _ncle(object):
	def __init__(self,N_cl,N_lat,
				 nn_list,cluster_list,
				 L_list,Ncl_list,Y):
		self._N_cl = N_cl
		self._N_lat = N_lat
		self._nn_list = nn_list
		self._cluster_list = cluster_list
		self._L_list = L_list
		self._Ncl_list = Ncl_list
		self._Y = Y


	@property
	def Nc(self):
		return self._L_list.shape[0]
	

	def get_W(self,O,out=None):
		result_dtype = _np.result_type(self._Y.dtype,O.dtype)

		if O.shape[0] != self._L_list.shape[0]:
			raise ValueError

		shape0 = O.shape
		shape = shape0[:1] + (-1,)

		if out is not None:
			if out.dtype != result_dtype:
				raise ValueError

			if out.shape != shape0:
				raise ValueError
		else:
			out = _np.zeros(shape0,dtype=result_dtype)

		O = O.reshape(shape)
		out = out.reshape(shape)

		_get_W(O,out,self._Y.data,self._Y.indices,self._Y.indptr)

		return out.reshape(shape0)

	def partial_sums(self,O):
		W = self.get_W(O)
		shape = W.shape[:1]+(-1,)
		Sn = _get_Sn(W.reshape(shape),self._L_list,self._Ncl_list)
		return Sn

	def bare_sums(self,O):
		return self.partial_sums(O).cumsum(axis=0)

	def wynn_sums(self,O,ncycle):
		if 2*ncycle >= O.shape[0]:
			raise ValueError

		p = self.bare_sums(O)

		nmax = p.shape[0]

		e0 = _np.zeros_like(p)
		e1 = p.copy()
		e2 = _np.zeros_like(e1)

		for k in range(1,2*ncycle+1,1):
			e2[0:nmax-k,...] = e0[1:nmax-k+1,...] + 1/(_np.diff(e1,axis=0)[0:nmax-k,...]+1.1e-15)

			e0[:] = e1[:]
			e1[:] = e2[:]
			e2[:] = 0


		return e1[:nmax-2*ncycle,...]

	def get_cluster_graph(self,ic):
		if type(ic) is not int:
			raise ValueError

		if ic < 0 or ic >= self.Nc:
			raise ValueError

		graph = []
		stack = []
		
		sites = self._cluster_list[ic,:].compressed()
		sites.sort()
		visited = set([])
		stack.append(sites[0])

		while(stack):
			i = stack.pop()
			a = _np.searchsorted(sites,i)

			for nn in self._nn_list[i,:]:
				if nn not in visited and nn in sites:
					b = _np.searchsorted(sites,nn)
					graph.append((a,b))
					stack.append(nn)

			visited.add(i)

		return ic,_np.array(sites),self._Ncl_list[ic],frozenset(graph)


	def __getitem__(self,key=None):
		if type(key) is int:
			yield self.get_cluster_graph(key)
		elif type(key) is slice:
			if key.start is None:
				start = 0
			else:
				start = (key.start)%len(self._L_list)

			if key.stop is None:
				stop = len(self._L_list)
			else:
				stop = (key.stop)%len(self._L_list)

			if key.step is None:
				step = 1
			else:
				step = key.step

			for i in range(start,stop,step):
				yield self.get_cluster_graph(i)
		else:
			try:
				iter_key = iter(key)
			except:
				raise ValueError("cannot interpret input: {}".format(key))

			for i in iter_key:
				yield self.get_cluster_graph(i)


class NLCE(_ncle):
	def __init__(self,N_cl,N_lat,nn_list,tr,pg):
	
		if nn_list.shape[0] != N_lat:
			raise ValueError

		if tr.shape[1] != N_lat:
			raise ValueError

		if pg.shape[1] != N_lat:
			raise ValueError

		nt_point = pg.shape[0]
		nt_trans = tr.shape[0]

		symm_list = ([process_map(p,0) for p in pg[:]]+
					 [process_map(p,0) for p in tr[:]] )

		maps,pers,qs,_ = zip(*symm_list)

		maps = _np.vstack(maps).astype(_np.int32)
		pers = _np.array(pers,dtype=_np.int32)
		qs   = _np.array(qs,dtype=_np.int32)

		n_maps = maps.shape[0]

		for j in range(n_maps-1):
			for i in range(j+1,n_maps,1):
				if _np.all(maps[j]==maps[i]):
					ValueError("repeated transformations in list of permutations for point group/translations.")

		nlce_core = nlce_core_wrap(N_cl,nt_point,nt_trans,maps,pers,qs,nn_list)

		clusters_list,L_list,Ncl_list,Y = nlce_core.calc_clusters()

		_ncle.__init__(self,N_cl,N_lat,nn_list,clusters_list,L_list,Ncl_list,Y)
		




