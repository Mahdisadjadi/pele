import numpy as np
import logging
from collections import namedtuple

#from bfgs import lineSearch, BFGS
from optimization_exceptions import LineSearchError
from pele.optimize import Result

__all__ = ["LBFGS"]

_logger = logging.getLogger("pele.optimize")


class LBFGS(object):
    """
    minimize a function using the LBFGS routine
    
    Parameters
    ----------
    X : array
        the starting configuration for the minimization
    pot :
        the potential object
    nsteps : int
        the maximum number of iterations
    tol : float
        the minimization will stop when the rms grad is less than tol
    iprint : int
        how often to print status information
    maxstep : float
        the maximum step size
    maxErise : float
        the maximum the energy is alowed to rise during a step.
        The step size will be reduced until this condition is satisfied.
    M : int
        the number of previous iterations to use in determining the optimal step
    rel_energy : bool
        if True, then maxErise the the *relative* maximum the energy is allowed
        to rise during a step
    H0 : float
        the initial guess for the inverse diagonal Hessian.  This particular
        implementation of LBFGS takes all the inverse diagonal components to be the same. 
    events : list of callables
        these are called after each iteration.  events can also be added using
        attachEvent()
    alternate_stop_criterion : callable
        this criterion will be used rather than rms gradiant to determine when
        to stop the iteration
    debug : 
        print debugging information
    logger : logger object
        messages will be passed to this logger rather than the default
    energy, gradient : float, float array
        the initial energy and gradient.  If these are both not None then the
        energy and gradient of the initial point will not be calculated, saving
        one potential call.
         
    Notes
    -----
    This each iteration of this minimization routine is composed of the 
    following parts
    
    1. determine a step size and direction using the LBFGS algorithm
    
    2. ensure the step size is appropriate (see maxErise and maxstep).
       Reduce the step size until conditions are satisfied.
    
    3. take step

    http://dx.doi.org/10.1007/BF01589116
    
    See Also
    --------
    MYLBFGS : this implemented in a compiled language
    lbfgs_py : a function wrapper
    
    """
    def __init__(self, X, pot, maxstep=0.1, maxErise=1e-4, M=4, 
                 rel_energy=False, H0=1., events=None,
                 alternate_stop_criterion=None, debug=False,
                 iprint=-1, nsteps=10000, tol=1e-6, logger=None,
                 energy=None, gradient=None,
                 ):
        self.X = X
        self.N = len(X)
        self.M = M 
        self.pot = pot
        if energy is not None and gradient is not None:
            self.energy = energy
            self.G = gradient
        else:
            self.energy, self.G = self.pot.getEnergyGradient(self.X)
        self.rms = np.linalg.norm(self.G) / np.sqrt(self.N)

        self.funcalls = 1
        self.maxstep = maxstep
        self.maxErise = maxErise
        self.rel_energy = rel_energy #use relative energy comparison for maxErise 
        self.events = events #a list of events to run during the optimization
        if self.events is None: self.events = []
        self.iprint = iprint
        self.nsteps = nsteps
        self.tol = tol
        if logger is None:
            self.logger = _logger
        else:
            self.logger = logger
    
        self.alternate_stop_criterion = alternate_stop_criterion
        self.debug = debug #print debug messages
        
        
        self.s = np.zeros([self.M, self.N])  #position updates
        self.y = np.zeros([self.M, self.N])  #gradient updates
#        self.a = np.zeros(self.M)  #approximation for the inverse hessian
        #self.beta = np.zeros(M) #working space
        
        if H0 is None:
            self.H0 = 1.
        else:
            self.H0 = H0
        if self.H0 < 1e-10:
            self.logger.warning("initial guess for inverse Hessian diagonal is negative or too small %s %s", 
                                self.H0, "resetting it to 1.")
            self.H0 = 1.
        self.rho = np.zeros(M)
        self.k = 0
        
        self.s[0,:] = self.X
        self.y[0,:] = self.G
        self.rho[0] = 0. #1. / np.dot(X,G)
        
        self.Xold = self.X.copy()
        self.Gold = self.G.copy()
        
        self.nfailed = 0
        
        self.iter_number = 0
        self.result = Result()
    
    def get_state(self):
        State = namedtuple("State", "s y rho k H0 Xold Gold")
        state = State(s=self.s.copy(), y=self.y.copy(),
                      rho=self.rho.copy(), k=self.k, H0=self.H0,
                      Xold=self.Xold.copy(), Gold=self.Gold.copy())
        return state
    
    def set_state(self, state):
        self.s = state.s
        self.y = state.y
        self.rho = state.rho
        self.k = state.k
        self.H0 = state.H0
        self.Xold = state.Xold
        self.Gold = state.Gold
        assert self.s.shape == (self.M, self.N)
        assert self.y.shape == (self.M, self.N)
        assert self.rho.shape == (self.M,)
        assert self.Xold.shape == (self.N,)
        assert self.Gold.shape == (self.N,)
        
    
    def getStep(self, X, G):
        """
        Calculate a step direction and step size using the 
        LBFGS algorithm
        
        http://en.wikipedia.org/wiki/Limited-memory_BFGS
        
        Liu and Nocedal 1989
        http://dx.doi.org/10.1007/BF01589116
        """
#        self.G = G #saved for the line search
        
        s = self.s
        y = self.y
        rho = self.rho
        M = self.M
        
        k = self.k
        ki = k % M #the index corresponding to k
        
        
        #we have a new X and G, save in s and y
        if k > 0:
            km1 = (k + M - 1) % M  #=k-1  cyclical
            s[km1,:] = X - self.Xold
            y[km1,:] = G - self.Gold
            
            YS = np.dot(s[km1,:], y[km1,:])
            if YS == 0.:
                self.logger.warning("resetting YS to 1 in lbfgs %s", YS)
                YS = 1.            
            rho[km1] = 1. / YS
            
            # update the approximation for the diagonal inverse hessian
            # scale H0 according to
            # H_k = YS/YY * H_0 
            # this is described in Liu and Nocedal 1989 
            # http://dx.doi.org/10.1007/BF01589116
            # note: for this step we assume H0 is always the identity
            YY = np.dot( y[km1,:], y[km1,:] )
            if YY == 0.:
                self.logger.warning("warning: resetting YY to 1 in lbfgs %s", YY)
                YY = 1.
            self.H0 = YS / YY

        self.Xold[:] = X[:]
        self.Gold[:] = G[:]

        
        q = G.copy()
        a = np.zeros(self.M)
        myrange = [ i % M for i in range(max([0, k - M]), k, 1) ]
        #print "myrange", myrange, ki, k
        for i in reversed(myrange):
            a[i] = rho[i] * np.dot( s[i,:], q )
            q -= a[i] * y[i,:]
        
        #z[:] = self.H0[ki] * q[:]
        z = q #q is not used anymore after this, so we can use it as workspace
        z *= self.H0
        for i in myrange:
            beta = rho[i] * np.dot( y[i,:], z )
            z += s[i,:] * (a[i] - beta)
        
        stp = -z.copy()
        
        if k == 0:
            #make first guess for the step length cautious
            gnorm = np.linalg.norm(G)
            stp *= min(gnorm, 1. / gnorm)
        
        self.k += 1
        return stp

    def adjustStepSize(self, X, E, G, stp):
        """
        We now have a proposed step.  This function will make sure it is 
        a good step and then take it.
        
        1) if the step is not anti-aligned with the gradient (i.e. downhill), then reverse the step
        
        2) if the step is larger than maxstep, then rescale the step
        
        3) calculate the energy and gradient of the new position
        
        4) if the step increases the energy by more than maxErise, 
            then reduce the step size and go to 3)
        
        5) if the step is reduced more than 10 times and the energy is still not acceptable
            increment nfail, reset the lbfgs optimizer and continue
            
        6) if nfail is greater than 5 abort the quench
                
        *The below is not implemented yet.  It's on the TODO list
        
        """
        f = 1.
        X0 = X.copy()
        G0 = G.copy()
        E0 = E
        
        if np.dot(G, stp) > 0:
            #print "overlap was negative, reversing step direction"
            stp = -stp
        
        stepsize = np.linalg.norm(stp)
        
        if f * stepsize > self.maxstep:
            f = self.maxstep / stepsize
        #print "dot(grad, step)", np.dot(G0, stp) / np.linalg.norm(G0)/ np.linalg.norm(stp)

        #self.nfailed = 0
        nincrease = 0
        while True:
            X = X0 + f * stp
            E, G = self.pot.getEnergyGradient(X)
            self.funcalls += 1

            # get the increase in energy            
            if self.rel_energy: 
                if E == 0: E = 1e-100
                dE = (E - E0)/abs(E)
                #print dE
            else:
                dE = E - E0

            # if the increase is greater than maxErise reduce the step size
            if dE <= self.maxErise:
                break
            else:
                if self.debug:
                    self.logger.info("warning: energy increased, trying a smaller step %s %s %s %s", E, E0, f*stepsize, nincrease)
                f /= 10.
                nincrease += 1
                if nincrease > 10:
                    break

        if nincrease > 10:
            self.nfailed += 1
            if self.nfailed > 10:
                raise(LineSearchError("lbfgs: too many failures in adjustStepSize, exiting"))

            # abort the linesearch, reset the memory and reset the coordinates            
            #print "lbfgs: having trouble finding a good step size. dot(grad, step)", np.dot(G0, stp) / np.linalg.norm(G0)/ np.linalg.norm(stp)
            self.logger.warning("lbfgs: having trouble finding a good step size. %s %s", f*stepsize, stepsize)
            self.reset()
            E = E0
            G = G0
            X = X0
            f = 0.
        
        self.stepsize = f * stepsize
        return X, E, G
    
    def reset(self):
        self.H0 = 1.
        self.k = 0
    
    def attachEvent(self, event):
        self.events.append(event)
    
    def one_iteration(self):
        """do one iteration of the lbfgs loop
        """
        stp = self.getStep(self.X, self.G)
        
        self.X, self.energy, self.G = self.adjustStepSize(self.X, self.energy, self.G, stp)
        
        self.rms = np.linalg.norm(self.G) / np.sqrt(self.N)

        
        if self.iprint > 0 and self.iter_number % self.iprint == 0:
            self.logger.info("lbfgs: %s %s %s %s %s %s %s %s %s", self.iter_number, "E", self.energy, 
                             "rms", self.rms, "funcalls", self.funcalls, "stepsize", self.stepsize)
        for event in self.events:
            event(coords=self.X, energy=self.energy, rms=self.rms)
  
        self.iter_number += 1
        return True

    def stop_criterion_satisfied(self):
        if self.alternate_stop_criterion is None:
            return self.rms < self.tol
        else:
            return self.alternate_stop_criterion(energy=self.energy, gradient=self.G, 
                                                 tol=self.tol, coords=self.X)

    
    def run(self):
        while self.iter_number < self.nsteps and not self.stop_criterion_satisfied():
            try:
                self.one_iteration()
            except LineSearchError:
                self.logger.error("problem with adjustStepSize, ending quench")
                self.rms = np.linalg.norm(self.G) / np.sqrt(self.N)
                self.logger.error("    on failure: quench step %s %s %s %s", self.iter_number, self.energy, self.rms, self.funcalls)
                self.result.message.append( "problem with adjustStepSize" )
                break
        
        return self.get_result()
            

    
    def run_old(self):
        """
        the main loop of the algorithm
        """
        res = Result()
        res.message = []
        tol = self.tol
        iprint = self.iprint
        nsteps = self.nsteps
                
        #iprint =40
        X = self.X
        sqrtN = np.sqrt(self.N)
        
        
        i = 1
        self.funcalls += 1
        e, G = self.pot.getEnergyGradient(X)
        rms = np.linalg.norm(G) / sqrtN
        res.success = False
        while i < nsteps:
            stp = self.getStep(X, G)
            
            try:
                X, e, G = self.adjustStepSize(X, e, G, stp)
            except LineSearchError:
                self.logger.error("problem with adjustStepSize, ending quench")
                rms = np.linalg.norm(G) / np.sqrt(self.N)
                self.logger.error("    on failure: quench step %s %s %s %s", i, e, rms, self.funcalls)
                res.message.append( "problem with adjustStepSize" )
                break
            #e, G = self.pot.getEnergyGradient(X)
            
            rms = np.linalg.norm(G) / np.sqrt(self.N)
    
            
            if iprint > 0:
                if i % iprint == 0:
                    self.logger.info("lbfgs: %s %s %s %s %s %s %s %s %s", i, "E", e, 
                                     "rms", rms, "funcalls", self.funcalls, "stepsize", self.stepsize)
            for event in self.events:
                event(coords=X, energy=e, rms=rms)
      
            if self.alternate_stop_criterion is None:
                i_am_done = rms < self.tol
            else:
                i_am_done = self.alternate_stop_criterion(energy=e, gradient=G, 
                                                          tol=self.tol, coords=X)
                
            if i_am_done:
                res.success = True
                break
            i += 1

        res.nsteps = i
        res.nfev = self.funcalls
        res.coords = X
        res.energy = e
        res.rms = rms
        res.grad = G
        res.H0 = self.H0
        return res
    
    def get_result(self):
        res = self.result
        res.nsteps = self.iter_number
        res.nfev = self.funcalls
        res.coords = self.X
        res.energy = self.energy
        res.rms = self.rms
        res.grad = self.G
        res.H0 = self.H0
        res.success = self.stop_criterion_satisfied()
        return res

#
# only testing stuff below here
#   

class PrintEvent:
    def __init__(self, fname):
        self.fout = open(fname, "w")
        self.coordslist = []

    def __call__(self, coords, **kwargs):
        from pele.printing.print_atoms_xyz import printAtomsXYZ as printxyz 
        printxyz(self.fout, coords)
        self.coordslist.append( coords.copy() )
        
    

def test(pot, natoms = 100, iprint=-1):    
    #X = bfgs.getInitialCoords(natoms, pot)
    #X += np.random.uniform(-1,1,[3*natoms]) * 0.3
    X = np.random.uniform(-1,1,[natoms*3])*(1.*natoms)**(1./3)*.5
    
    runtest(X, pot, natoms, iprint)

def runtest(X, pot, natoms = 100, iprint=-1):
    tol = 1e-5

    Xinit = np.copy(X)
    e, g = pot.getEnergyGradient(X)
    print "energy", e
    
    lbfgs = LBFGS(X, pot, maxstep = 0.1, tol=tol, iprint=iprint, nsteps=10000)
    printevent = PrintEvent( "debugout.xyz")
    lbfgs.attachEvent(printevent)
    
    ret = lbfgs.run()
    print "done", ret
    
    print "now do the same with scipy lbfgs"
    from pele.optimize import lbfgs_scipy as quench
    ret = quench(Xinit, pot, tol = tol)
    print ret 
    
    if False:
        print "now do the same with scipy bfgs"
        from pele.optimize import bfgs as oldbfgs
        ret = oldbfgs(Xinit, pot, tol = tol)
        print ret    
    
    if False:
        print "now do the same with gradient + linesearch"
        import _bfgs
        gpl = _bfgs.GradientPlusLinesearch(Xinit, pot, maxstep = 0.1)  
        ret = gpl.run(1000, tol = 1e-6)
        print ret 
            
    if False:
        print "calling from wrapper function"
        from pele.optimize import lbfgs_py
        ret = lbfgs_py(Xinit, pot, tol = tol)
        print ret


    try:
        import pele.utils.pymolwrapper as pym
        pym.start()
        for n, coords in enumerate(printevent.coordslist):
            coords = coords.reshape([-1, 3])
            pym.draw_spheres(coords, "A", n)
    except ImportError:
        print "error loading pymol"

        
if __name__ == "__main__":
    from pele.potentials.lj import LJ
    from pele.potentials.ATLJ import ATLJ
    pot = ATLJ()

    #test(pot, natoms=3, iprint=1)
    
#    coords = np.loadtxt("coords")
    natoms = 10
    coords = np.random.uniform(-1,1,natoms*3)
    print coords.size
    coords = np.reshape(coords, coords.size)
    print coords
    runtest(coords, pot, natoms=3, iprint=1)
    











