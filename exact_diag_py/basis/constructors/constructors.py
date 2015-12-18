from fortran_wrap import *
from numpy import dtype as _dtype


# open boundary conditions
fortran_RefState_P={"float32":s_refstate_p,"float64":d_refstate_p,"complex64":c_refstate_p,"complex128":z_refstate_p}
fortran_RefState_Z={"float32":s_refstate_z,"float64":d_refstate_z,"complex64":c_refstate_z,"complex128":z_refstate_z}
fortran_RefState_PZ={"float32":s_refstate_pz,"float64":d_refstate_pz,"complex64":c_refstate_pz,"complex128":z_refstate_pz}
fortran_RefState_P_Z={"float32":s_refstate_p_z,"float64":d_refstate_p_z,"complex64":c_refstate_p_z,"complex128":z_refstate_p_z}

# periodic boundary conditions
fortran_RefState_T={"float32":s_refstate_t,"float64":d_refstate_t,"complex64":c_refstate_t,"complex128":z_refstate_t}


fortran_SpinOp={"float32":s_spinop,"float64":d_spinop,"complex64":c_spinop,"complex128":z_spinop}

class BasisFortranError(Exception):
	# this class defines an exception which can be raised whenever there is some sort of error which we can
	# see will obviously break the code. 
	def __init__(self,message):
		self.message=message
	def __str__(self):
		return self.message


def RefState_M(basis,col,*args):
	refstate(basis,col)

def RefState_Z(basis,col,L,N,ME,**symm):
	zblock=symm.get("zblock")
	dtype=str(ME.dtype)
	fortran_RefState_Z[dtype](N,basis,col,ME,L,zblock)


def RefState_P(basis,col,L,N,ME,**symm):
	pblock=symm.get("pblock")
	dtype=str(ME.dtype)
	fortran_RefState_P[dtype](N,basis,col,ME,L,pblock)


def RefState_PZ(basis,col,L,N,ME,**symm):
	pzblock=symm.get("pzblock")
	dtype=str(ME.dtype)
	fortran_RefState_PZ[dtype](N,basis,col,ME,L,pzblock)


def RefState_P_Z(basis,col,L,N,ME,**symm):
	zblock=symm.get("zblock")
	pblock=symm.get("pblock")
	dtype=str(ME.dtype)
	fortran_RefState_P_Z[dtype](N,basis,col,ME,L,pblock,zblock)

def RefState_T(basis,col,L,N,ME,**symm):
	a=symm.get("a")
	kblock=symm.get("kblock")
	dtype=str(ME.dtype)
	fortran_RefState_T[dtype](N,basis,col,ME,L,kblock,a)
	



def SpinOp(basis,opstr,indx,dtype):
	dtype=str(_dtype(dtype))
	ME,col,error=fortran_SpinOp[dtype](basis,opstr,indx)
	if error != 0:
		if error == 1:
			raise BasisFortranError("opstr character not regcognized.")
		elif error == -1:
			raise BasisFortranError("attemping to use real hamiltonian with complex matrix elements.")

	return ME,col


	
