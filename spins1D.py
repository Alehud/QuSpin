import sys # needed for sys.stop('error message')
#local modules:
from Basis import Basis1D
from py_lapack import eigh # used to diagonalize hermitian and symmetric matricies

#python 2.7 modules
#from memory_profiler import profile
#from pympler.asizeof import asizeof

from scipy.linalg import norm
from scipy.sparse import coo_matrix	# needed as the initial format that the Hamiltonian matrices are stored as
from scipy.sparse import csr_matrix	# the final version the sparse matrices are stored as, good format for dot produces with vectors.
from scipy.sparse.linalg  import eigsh	# needed for the sparse linear algebra packages
from scipy.integrate import complex_ode,ode	# ode solver used in evolve wave function.
from numpy import concatenate, isscalar, real, vdot, asarray, array, int32, int64, float32, float64, complex64, complex128
from copy import deepcopy
from sys import maxint
from functools import partial
from multiprocessing import Pool,cpu_count



#global names:
supported_dtypes=(float32, float64, complex64, complex128)


#@profile
def StaticH(B,static,dtype):
	"""
	args:
		static=[[opstr_1,indx_1],...,[opstr_n,indx_n]], list of opstr,indx to add up for static piece of Hamiltonian.
		dtype = the low level C-type which the matrix should store its values with.
	returns:
		H: a csr_matrix representation of the list static

	description:
		this function takes the list static and creates a list of matrix elements is coordinate format. it does
		this by calling the basis method Op which takes a state in the basis, acts with opstr and returns a matrix 
		element and the state which it is connected to. This function is called for every opstr in list static and for every 
		state in the basis until the entire hamiltonian is mapped out. It takes those matrix elements (which need not be 
		sorted or even unique) and creates a coo_matrix from the scipy.sparse library. It then converts this coo_matrix
		to a csr_matrix class which has optimal sparse matrix vector multiplication.
	"""

	p=Pool(processes=cpu_count())
	H=coo_matrix(([],([],[])),shape=(B.Ns,B.Ns),dtype=dtype) #
	st=xrange(B.Ns) # iterator which loops over the index of the reference states of the basis B.
	for i in xrange(len(static)): 
		List=static[i]
		opstr=List[0]
		bonds=List[1]
		for bond in bonds:
			J=bond[0]
			indx=bond[1:]
			Op=partial(B,J,opstr,indx)
			ME_list=p.map(Op,st)
			ME_list=asarray(ME_list)
			H.data=concatenate((H.data,ME_list[:,0]))
			H.row=concatenate((H.row,real(ME_list[:,1])))
			H.col=concatenate((H.col,real(ME_list[:,2])))
			H.sum_duplicates() # sum duplicate matrix elements
			print H.data.nbytes/(1024.0)**2
			

	if static:
		H=H.tocsr() # convert to csr_matrix
		H.sum_duplicates() # sum duplicate matrix elements
		H.eliminate_zeros() # remove all zero matrix elements
		return H 
	else: # else return None which indicates there is no static part of Hamiltonian.
		return None








def DynamicHs(B,dynamic,dtype):
	"""
	args:
	dynamic=[[opstr_1,indx_1,func_1],...,[opstr_n,indx_n,func_1]], list of opstr,indx and functions to drive with
	dtype = the low level C-type which the matrix should store its values with.

	returns:
	tuple((func_1,H_1),...,(func_n,H_n))

	H_i: a csr_matrix representation of opstr_i,indx_i
	func_i: callable function of time which is the drive term in front of H_i

	description:
		This function works the same as static, but instead of adding all of the elements 
		of the dynamic list together, it returns a tuple which contains each individual csr_matrix 
		representation of all the different driven parts. This way one can construct the time dependent 
		Hamiltonian simply by looping over the tuple returned by this function. 
	"""

	p=Pool(processes=cpu_count())
	Dynamic_Hs=[]
	st=[ k for k in xrange(B.Ns) ]
	for i in xrange(len(dynamic)):
		H=coo_matrix(([],([],[])),shape=(B.Ns,B.Ns),dtype=dtype)
		List=dynamic[i]
		opstr=List[0]
		bonds=List[1]
		for bond in bonds:
			J=bond[0]
			indx=bond[1:]
			Op=partial(B,J,opstr,indx)
			ME_list=asarray(p.map(Op,st))
			H.data=concatenate((H.data,ME_list[:,0]))
			H.row=concatenate((H.row,real(ME_list[:,1])))
			H.col=concatenate((H.col,real(ME_list[:,2])))
	
		H=H.tocsr()
		H.sum_duplicates()
		H.eliminate_zeros()
		Dynamic_Hs.append((List[2],H))


	return tuple(Dynamic_Hs)










class Hamiltonian1D:
	def __init__(self,static,dynamic,L,dtype=complex128,**basis_params):
		"""
		This function intializes the Hamtilonian. You can either initialize with symmetries, or an instance of Basis1D.
		Note that if you initialize with a basis it will ignore all symmetry inputs.
		"""
		basis=basis_params.get('basis')
		if basis is None: basis=Basis1D(L,**basis_params)

		if not isinstance(basis,Basis1D):
			raise TypeError('basis is not instance of Basis1D')
		if dtype not in supported_dtypes:
			raise TypeError('Hamiltonian1D does not support type: '+str(dtype))


		self.L=L
		self.Ns=basis.Ns
		self.dtype=dtype
		if self.Ns > 0:
			self.Static_H=StaticH(basis,static,dtype)
			self.Dynamic_Hs=DynamicHs(basis,dynamic,dtype)
			self.shape=(self.Ns,self.Ns)
			self.sum_duplicates()



	def sum_duplicates(self):
		"""
		description:
			This function consolidates the list of Dynamic_Hs, combining matrices which have the same driving function.
		"""
		self.Dynamic_Hs=list(self.Dynamic_Hs)
		l=len(self.Dynamic_Hs)
		i=j=0;
		while i < l:
#			print i,l
			while j < l:
#				print "\t",i,j,l
				if i != j:
					ele1=self.Dynamic_Hs[i]; ele2=self.Dynamic_Hs[j]
					if ele1[0] == ele2[0]:
						self.Dynamic_Hs.pop(j)
						i=self.Dynamic_Hs.index(ele1)
						self.Dynamic_Hs.pop(i)
						ele1=list(ele1)
						ele1[1]+=ele2[1]
						self.Dynamic_Hs.insert(i,tuple(ele1))
				l=len(self.Dynamic_Hs); j+=1
			i+=1;j=0
		self.Dynamic_Hs=tuple(self.Dynamic_Hs)



	def tocsr(self,time=0):
		"""
		args:
			time=0, the time to evalute drive at.

		description:
			this function simply returns a copy of the Hamiltonian as a csr_matrix evaluated at the desired time.
		"""
		if self.Ns <= 0:
			return csr_matrix(asarray([[]]))
		if not isscalar(time):
			raise NotImplementedError

		if self.Static_H is None: # if there isn't a static Hamiltonian...
			for ele in self.Dynamic_Hs:
				H += ele[1]*ele[0](time)
		else: # if there is..
			H=self.Static_H	
			for ele in self.Dynamic_Hs:
				H += ele[1]*ele[0](time)

		return H


	def todense(self,time=0):
		"""
		args:
			time=0, the time to evalute drive at.

		description:
			this function simply returns a copy of the Hamiltonian as a dense matrix evaluated at the desired time.
			This function can overflow memory if not careful.
		"""
		if self.Ns <= 0:
			return matrix([])
		if not isscalar(time):
			raise NotImplementedError

		return self.tocsr(time=time).todense()





	def dot(self,V,time=0):
		"""
		args:
			V, the vector to multiple with
			time=0, the time to evalute drive at.

		description:
			This function does the spare matrix vector multiplication of V with the Hamiltonian evaluated at 
			the specified time. It is faster in this case to multiple each individual parts of the Hamiltonian 
			first, then add all those vectors together.
		"""
		if self.Ns <= 0:
			return array([])
		if not isscalar(time):
			raise NotImplementedError

		V=asarray(V)
		if self.Static_H is None: # if there isn't a static Hamiltonian...
			for ele in self.Dynamic_Hs:
				J=ele[0](time)
				V_dot += J*(ele[1].dot(V))
		else: # if there is...
			V_dot = self.Static_H.dot(V)	
			for ele in self.Dynamic_Hs:
				J=ele[0](time)
				V_dot += J*(ele[1].dot(V))

		return V_dot





	def me(self,Vl,Vr,time=0):
		"""
		args:
			Vl, the vector to multiple with on left side
			Vr, the vector to multiple with on the right side
			time=0, the time to evalute drive at.

		description:
			This function takes the matrix element of the Hamiltonian at the specified time
			between Vl and Vr.
		"""
		if self.Ns <= 0:
			return None

		Vl=asarray(Vl)
		Vr=asarray(Vr)
		HVr=self.dot(Vr,time=time)
		ME=vdot(Vl,HVr)
		return ME[0]





	def SparseEV(self,time=0,k=6,sigma=None,which='SA',maxiter=maxint/100):
		"""
		args:
			time=0, the time to evalute drive at.
			other arguements see documentation: http://docs.scipy.org/doc/scipy-0.14.0/reference/generated/scipy.sparse.linalg.eigsh.html
			
		description:
			function which diagonalizes hamiltonian using sparse methods
			solves for eigen values and eigen vectors, but can only solve for a few of them accurately.
			uses the scipy.sparse.linalg.eigsh function which is a wrapper for ARPACK
		"""
		if self.Ns <= 0:
			return array([]), array([[]])

		return eigsh(self.tocsr(time=time),k=k,sigma=sigma,which=which,maxiter=maxiter)





	def DenseEV(self,time=0):
		"""
		args:
			time=0, time to evaluate drive at.

		description:
			function which diagonalizes hamiltonian using dense methods solves for eigen values. 
			uses wrapped lapack functions which are contained in module py_lapack
		"""
		if self.Ns <= 0:
			return array([])

		return eigh(self.todense(time=time),JOBZ='N')





	def DenseEE(self,time=0):
		"""
		args:
			time=0, time to evaluate drive at.

		description:
			function which diagonalizes hamiltonian using dense methods solves for eigen values 
			and eigen vectors. uses wrapped lapack functions which are contained in module py_lapack
		"""
		if self.Ns <= 0:
			return array([]), array([[]])

		return eigh(self.todense(time=time))





	def evolve(self,v0,t0,time,real_time=True,verbose=False,atol=10**(-15),rtol=10**(-15),nsteps=maxint/100,**integrator_params):
		"""
		args:
			v0, intial wavefunction to evolve.
			t0, intial time 
			time, iterable or scalar, or time to evolve v0 to
			real_time, evolve real or imaginary time
			verbose, print times out as you evolve
			**integrator_params, the parameters used for the dop853 explicit rung-kutta solver.
			see documentation http://docs.scipy.org/doc/scipy-0.16.0/reference/generated/scipy.integrate.ode.html

		description:
			This function uses complex_ode to evolve an input wavefunction.
		"""
		if self.Ns <= 0:
			return array([])

		v0=asarray(v0)

		if real_time:
			solver=complex_ode(lambda t,y:-1j*self.dot(y,time=t))
		else:
			solver=complex_ode(lambda t,y:-self.dot(y,time=t))

		solver.set_integrator("dop853",atol=atol,rtol=rtol,nsteps=nsteps,**integrator_params)
		solver.set_initial_value(v0,t=t0)
		
		if isscalar(time):
			if time==t0: return v0
			solver.integrate(time)
			if solver.successful():
				return solver.y
			else:
				raise RuntimeError('failed to integrate')		
		else:
			sol=[]
			for t in time:
				if verbose: print t
				if t==t0: 
					sol.append(v0)
					continue
				solver.integrate(t)
				if solver.successful():
					sol.append(solver.y)
				else:
					raise RuntimeError('failed to integrate')
			return sol





	def exp(self,V,z,time=0,n=1,atol=10**(-8)):
		"""
		args:
			V, vector to apply the matrix exponential on.
			a, the parameter in the exponential exp(aH)V
			time, time to evaluate drive at.
			n, the number of steps to break the expoential into exp(aH/n)^n V
			error, if the norm the vector of the taylor series is less than this number
			then the taylor series is truncated.

		description:
			this function computes exp(zH)V as a taylor series in aH.
		"""
		if self.Ns <= 0:
			return array([])
		if not isscaler(time):
			raise NotImplementedError

		if n <= 0: raise ValueError('n must be > 0')

		H=self.tocsr(time=time)

		V=asarray(V)
		for j in xrange(n):
			V1=array(V)
			e=1.0; i=1		
			while e > error:
				V1=(z/(n*i))*H.dot(V1)
				V+=V1
				if i%2 == 0:
					e=norm(V1)
				i+=1
		return V


	def __call__(self,time):
		return self.tocsr(time=time)


	def __add__(self,other):
		if isinstance(other,Hamiltonian1D):
			if self.Ns != other.Ns: raise ValueError('dimension mismatch')
			new=deepcopy(other)
			new.Static_H+=self.Static_H
			new.Dynamic_Hs+=self.Dynamic_Hs
			new.sum_duplicates()
			return new
		else:
			raise NotImplementedError


	def __sub__(self,other):
		if isinstance(other,Hamiltonian1D):
			if self.Ns != other.Ns: raise ValueError('dimension mismatch')
			new=deepcopy(other)
			new.Static_H-=self.Static_H
			for ele in self.Dynamic_Hs:
				new.Dynamic_Hs.append((ele1[0],-ele[1]))
			new.sum_duplicates()
			return new
		else:
			raise NotImplementedError


	



