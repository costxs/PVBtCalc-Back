import numpy as np

ROCKFLOWFRACTION = {
    'Indiana Limestone':1, 
    'Edwards Yellow':0.91,
    'Austin Chalk':0.92,
    'Winterest Limestone':0.64,
    'Desert Pink':0.75,
    'Edwards White':0.52,
        }

class RockType:
    Indiana_Limestone = 'Indiana Limestone'
    Edwards_Yellow = 'Edwards Yellow'
    Austin_Chalk = 'Austin Chalk'
    Winterest_Limestone = 'Winterest Limestone'
    Desert_Pink = 'Desert Pink'
    Edwards_White = 'Edwards White'

class AcidSetup:
    def __init__(self, n, a, b, k0, acid_concentration) -> None:
        self.n = n
        self.a = a
        self.b = b
        self.k0 = k0
        self.acid_concentration = acid_concentration

class HCLwithout(AcidSetup):
    def __init__(self, acid_concentration) -> None: 
        super().__init__(
            n=0.65, 
            a=2.68*10**(-4), 
            b=17.3, k0=2.43*10**7, 
            acid_concentration = acid_concentration
            )

class HCLwith(AcidSetup):
    def __init__(self, acid_concentration) -> None: 
        super().__init__(
            n=0.65, 
            a=5.10*10**(-4), 
            b=35.1, k0=2.43*10**6,
            acid_concentration = acid_concentration
            )

class HCLemulsified(AcidSetup):
    def __init__(self, acid_concentration) -> None: 
        super().__init__(
            n=0.65, a=4.61*10**(-4), 
            b=15.5, k0=2.85*10**7, 
            acid_concentration = acid_concentration
            )

class AcidType:
    HCl = HCLwithout
    HClWithInibthorCorrosion = HCLwith
    HClEmulsified = HCLemulsified

    @staticmethod
    def getAcidTypeByStr(acid_type: str):
        acid_types = {
            "HCl": AcidType.HCl,
            "HCl With Inibithor Corrosion": AcidType.HClWithInibthorCorrosion,
            "HCl Emulsified": AcidType.HClEmulsified,
        }
        return acid_types.get(acid_type)



class CoreGeometry:
    """
    :param core_diamater: m (meter)
    :param core_length: m (meter)
    :param core_porosity: fraction

    """
    def __init__(
            self,
            core_diameter,
            core_length,
            core_porosity,
            rock_type : RockType,
    ):
        self.core_diameter = core_diameter
        self.core_length = core_length
        self.core_porosity = core_porosity
        self.characteristic_length = 1
        self.core_radius = (self.core_diameter / 2) / self.characteristic_length
        self.dimensionless_length = self.core_length /self.characteristic_length
        self.rock_type = rock_type


class PVBtSetup:
    """
    :param temperature: K (Kelvin)
    :param flowrate: m^3/s (Cubic meter per second)
    """
    def __init__(
            self,
            acidtype: AcidType,
            acid_concentration: float,
            core_diameter: float,
            core_length: float,
            core_porosity: float,
            rock_type: RockType,
            temperature,
            flowrate,
            ):
        self.acidsetup = acidtype(acid_concentration)
        self.core_geometry = CoreGeometry(
            core_diameter, 
            core_length, 
            core_porosity, 
            rock_type,
            )
        self.temperature = temperature
        self.flowrate = flowrate
        self.difisioncoefficient = None
        self.injectionfacecross = None
        self.flowfraction = None
        self.acid_density = None
        self.acid_gravimetric_dissolving_power = None
        self.acid_volumetric_dissolving_power = None
        self.acid_volumetric_dissolving_power100 = None
        self.SetDifusionCoeficient()
        self.SetInjectionFaceCrossSectionalArea()
        self.SetFlowfraction()
        self.SetAcidDensity()
        self.SetAcidGravimetricDissolvingPower()
        self.SetAcidVolumetricDissolvingPower()
        self.SetAcidVolumetricDissolvingPower100()


    def SetDifusionCoeficient(self):
        T = self.temperature
        Ca0 = self.acidsetup.acid_concentration
        self.difisioncoefficient = np.exp((-2270/T)+1.326*Ca0-12.11)

    def SetInjectionFaceCrossSectionalArea(self):
        r = self.core_geometry.core_radius
        self.injectionfacecross = np.pi*(r**2)
    
    def SetFlowfraction(self):
        for key, value in ROCKFLOWFRACTION.items():
            if self.core_geometry.rock_type == key:
                self.flowfraction = value

    def SetAcidDensity(self):
        #acid density unity (g/cm3)
        t = self.temperature - 273.15 #celsius temperature
        Ca0 = self.acidsetup.acid_concentration
        self.acid_density = 1.00683961828436 + 0.00507208224518196*Ca0*100 -0.00050572878832986*t


    def SetAcidGravimetricDissolvingPower(self):
        """
        """
        Ca0 = self.acidsetup.acid_concentration
        vm = 1
        MWm = 100.1 #for CaCO3
        va = 2
        MWa = 36.5 #for HCl
        self.acid_gravimetric_dissolving_power = Ca0 * ((vm*MWm)/(va*MWa))

    def SetAcidVolumetricDissolvingPower(self):
        """
        roa unity (lb/ft3)
        rom unity (lb/ft3)
        """
        beta = self.acid_gravimetric_dissolving_power
        roa = self.acid_density * 62.428 # convert acid density by g/cm3 to lbm/ft3
        rom = 169 # CaCO3 density in lbm/ft3
        self.acid_volumetric_dissolving_power = beta * (roa/rom)
    
    def SetAcidVolumetricDissolvingPower100(self):
        # Acid Volumetric Dissolving Power at HCl 100%
        Xp = self.acid_volumetric_dissolving_power
        Ca0 = self.acidsetup.acid_concentration
        self.acid_volumetric_dissolving_power100 = Xp/Ca0

class PVBt:
    def __init__(self, PVBtSetup: PVBtSetup):
        self.PVBtSetup = PVBtSetup
        self.InterticialVelocityCalculator()
        self.DarcyVelocityCalculator()
        self.WormholeVelocityCalculator()
        self.DamkholerNumberCalculator()
        self.KeffCalculator()
        self.InverseDamkholerCalculator()
        self.DimensionlessVelocityCalculator()
        self.PoreVolumeTobreakthroughCalculator()
        self.AcidVolumeToBtCalculator()
        self.TimeToBtCalculator()

    def InterticialVelocityCalculator(self):
        # Interticial Velocity unity (m/s)
        q0 = self.PVBtSetup.flowrate
        Ao = self.PVBtSetup.injectionfacecross
        phi = self.PVBtSetup.core_geometry.core_porosity
        self.interticial_velocity = q0/(Ao*phi)
        return self.interticial_velocity
    
    def DarcyVelocityCalculator(self):
        # Darcy velocity unity (m/s)
        q0 = self.PVBtSetup.flowrate
        Ao = self.PVBtSetup.injectionfacecross
        self.darcy_velocity = q0/Ao
        return self.darcy_velocity
    
    def WormholeVelocityCalculator(self):
        # Velocity in the wormhole unity (m/s)
        Dv = self.darcy_velocity
        a = self.PVBtSetup.acidsetup.a
        Ao = self.PVBtSetup.injectionfacecross
        n = self.PVBtSetup.acidsetup.n
        b = self.PVBtSetup.acidsetup.b
        self.wormhole_velocity = Dv / ((a*(Ao**n)/Ao)+(b*Dv))
        return self.wormhole_velocity
    
    def DamkholerNumberCalculator(self):
        # Damkholer number unity (dimensionless)
        k0 = self.PVBtSetup.acidsetup.k0
        Dm = self.PVBtSetup.difisioncoefficient
        L = self.PVBtSetup.core_geometry.characteristic_length
        Wv = self.wormhole_velocity
        self.damkholer_number = k0*Dm*L/Wv
        return self.damkholer_number
    
    def KeffCalculator(self):
        # Keff unity (need to investigate)
        k0 = self.PVBtSetup.acidsetup.k0
        Dm = self.PVBtSetup.difisioncoefficient
        self.keff = k0*Dm
        return self.keff
    
    def InverseDamkholerCalculator(self):
        # inverse damkholer number unity (dimensionless)
        Dn = self.damkholer_number
        self.inverse_damkholer_number = 1/Dn
        return self.inverse_damkholer_number
    
    def DimensionlessVelocityCalculator(self):
        # dimensionless velocity unity (dimensionless)
        Wv = self.wormhole_velocity
        Dv = self.darcy_velocity
        self.dimensionless_velocity = Wv/Dv
        return self.dimensionless_velocity
    
    def PoreVolumeTobreakthroughCalculator(self):
        # Pore Volume to Breakthrough unity (dimensionless)
        ff = self.PVBtSetup.flowfraction
        phi = self.PVBtSetup.core_geometry.core_porosity
        Dn = self.damkholer_number
        Ca0 = self.PVBtSetup.acidsetup.acid_concentration
        lamb = self.PVBtSetup.core_geometry.dimensionless_length
        X = self.PVBtSetup.acid_volumetric_dissolving_power100
        diV = self.dimensionless_velocity
        self.pore_volume_to_breaktrhrough = ff * (1-phi) * (np.exp(Dn*lamb)-1) / (phi*lamb*Ca0*X*diV*Dn)
        return  self.pore_volume_to_breaktrhrough
    
    def AcidVolumeToBtCalculator(self):
        # Acid volume to BT unity (cm^3)
        PVBt = self.pore_volume_to_breaktrhrough
        Ca0 = self.PVBtSetup.acidsetup.acid_concentration
        Ao = self.PVBtSetup.injectionfacecross
        l = self.PVBtSetup.core_geometry.core_length
        self.acid_volume_to_bt = PVBt * Ca0 * Ao * l * 1000000
        return self.acid_volume_to_bt
    
    def TimeToBtCalculator(self):
        ff = self.PVBtSetup.flowfraction
        phi = self.PVBtSetup.core_geometry.core_porosity
        Dn = self.damkholer_number
        lamb = self.PVBtSetup.core_geometry.dimensionless_length
        Ca0 = self.PVBtSetup.acidsetup.acid_concentration
        X = self.PVBtSetup.acid_volumetric_dissolving_power100
        keff = self.keff
        self.time_to_bt = ff * (1-phi)*(np.exp(Dn*lamb)-1) / (Ca0*X*keff)
        return self.time_to_bt



class PVBtMaster:

    def __init__(
            self,
            acidtype: AcidType,
            acid_concentration: float,
            core_diameter: float,
            core_length: float,
            core_porosity: float,
            rock_type: RockType,
            temperature,
            flowrate,
            minimun_temperature = None,
            minimun_flowrate = None,
            step_numbers = None,
            minimum_diameter = None,
            mininum_length = None,
            minimum_porosity = None,
            minimum_concentration = None,
    ):
        self.ConvertUnits(core_diameter, core_length, temperature, flowrate, minimun_flowrate, minimun_temperature, minimum_diameter, mininum_length)
        self.acidtype = acidtype
        self.acid_concentration = acid_concentration
        self.core_porosity = core_porosity
        self.rock_type = rock_type
        self.step_numbers = step_numbers
        self.mininum_porosity = minimum_porosity
        self.minimum_concentration = minimum_concentration

    def ConvertUnits(self, core_diameter, core_length, temperature, flowrate, minimun_flowrate, minimum_temperature, minimum_diameter, minimum_length,):
        self.core_diameter = core_diameter / 39.37
        self.minimum_diameter = minimum_diameter / 39.37 if minimum_diameter else None
        self.core_length = core_length / 39.37
        self.minimum_length = minimum_length / 39.37 if minimum_length else None
        self.temperature = temperature + 273.15
        self.minimum_temperature = minimum_temperature + 273.15 if minimum_temperature else None
        self.flowrate = (flowrate/60)*(10**(-6))
        self.mininum_flowrate = ((minimun_flowrate/60)*(10**(-6))) if minimun_flowrate else None

    def PVBtPointCalculator(self):
        setup = PVBtSetup(
            self.acidtype,
            self.acid_concentration,
            self.core_diameter,
            self.core_length,
            self.core_porosity,
            self.rock_type,
            self.temperature,
            self.flowrate,
        )

        PVBtcalculator = PVBt(setup)
        return PVBtcalculator.PoreVolumeTobreakthroughCalculator()

    def PVBtPointCalculatorWithDetails(self):
        
        setup = PVBtSetup(
            self.acidtype,
            self.acid_concentration,
            self.core_diameter,
            self.core_length,
            self.core_porosity,
            self.rock_type,
            self.temperature,
            self.flowrate,
        )

        PVBtcalculator = PVBt(setup)
        return (
            PVBtcalculator.PoreVolumeTobreakthroughCalculator(), 
            self.flowrate, 
            PVBtcalculator.InterticialVelocityCalculator(),
            PVBtcalculator.InverseDamkholerCalculator(),
            PVBtcalculator.AcidVolumeToBtCalculator(),
            PVBtcalculator.TimeToBtCalculator(),
            PVBtcalculator.WormholeVelocityCalculator(),
            PVBtcalculator.DarcyVelocityCalculator(),
        )

    def getSetup(self):
        setup = PVBtSetup(
            self.acidtype,
            self.acid_concentration,
            self.core_diameter,
            self.core_length,
            self.core_porosity,
            self.rock_type,
            self.temperature,
            self.flowrate,
        )

        
        return setup
    
    def PVBtCurveCalculator(self):

        flowPoints = np.linspace(self.mininum_flowrate, self.flowrate, self.step_numbers)
        FlowratePoints = []
        PVBtPoints = []
        for q in flowPoints:
            setup = PVBtSetup(
                self.acidtype,
                self.acid_concentration,
                self.core_diameter,
                self.core_length,
                self.core_porosity,
                self.rock_type,
                self.temperature,
                q,
            )
            PVBtCalculator = PVBt(setup)
            PVBtPoints.append(PVBtCalculator.PoreVolumeTobreakthroughCalculator())

        for point in flowPoints:
            FlowratePoints.append( ((point*60)/(10**(-6))) )
        return PVBtPoints, FlowratePoints
    
    def PVBtCurveCalculatorWhiteDetails(self):

        flowPoints = np.linspace(self.mininum_flowrate, self.flowrate, self.step_numbers)
        FlowratePoints = []
        PVBtPoints = []
        intersticialVelocity = []
        iDa = []
        volumeToBt = []
        timeToBt = []
        wormholeVelocity = []
        darcyVelocity = []
        for q in flowPoints:
            setup = PVBtSetup(
                self.acidtype,
                self.acid_concentration,
                self.core_diameter,
                self.core_length,
                self.core_porosity,
                self.rock_type,
                self.temperature,
                q,
            )
            PVBtCalculator = PVBt(setup)
            PVBtPoints.append(PVBtCalculator.PoreVolumeTobreakthroughCalculator())
            intersticialVelocity.append(PVBtCalculator.InterticialVelocityCalculator())
            iDa.append(PVBtCalculator.InverseDamkholerCalculator())
            volumeToBt.append(PVBtCalculator.AcidVolumeToBtCalculator())
            timeToBt.append(PVBtCalculator.TimeToBtCalculator())
            wormholeVelocity.append(PVBtCalculator.WormholeVelocityCalculator())
            darcyVelocity.append(PVBtCalculator.DarcyVelocityCalculator())

        for point in flowPoints:
            FlowratePoints.append( ((point*60)/(10**(-6))) )
        return PVBtPoints, FlowratePoints, intersticialVelocity, iDa, volumeToBt, timeToBt, wormholeVelocity, darcyVelocity
    
    def PVBtCurveAnaliticalWhiteDetailsTemp(self):

        analicalPoints = np.linspace(self.minimum_temperature, self.temperature, self.step_numbers)
        analitical = []
        PVBtPoints = []
        intersticialVelocity = []
        iDa = []
        volumeToBt = []
        timeToBt = []
        wormholeVelocity = []
        darcyVelocity = []
        for t in analicalPoints:
            setup = PVBtSetup(
                self.acidtype,
                self.acid_concentration,
                self.core_diameter,
                self.core_length,
                self.core_porosity,
                self.rock_type,
                t,
                self.flowrate,
            )
            PVBtCalculator = PVBt(setup)
            PVBtPoints.append(PVBtCalculator.PoreVolumeTobreakthroughCalculator())
            intersticialVelocity.append(PVBtCalculator.InterticialVelocityCalculator())
            iDa.append(PVBtCalculator.InverseDamkholerCalculator())
            volumeToBt.append(PVBtCalculator.AcidVolumeToBtCalculator())
            timeToBt.append(PVBtCalculator.TimeToBtCalculator())
            wormholeVelocity.append(PVBtCalculator.WormholeVelocityCalculator())
            darcyVelocity.append(PVBtCalculator.DarcyVelocityCalculator())
            analitical.append(t - 273.15)

        return PVBtPoints, analitical, intersticialVelocity, iDa, volumeToBt, timeToBt, wormholeVelocity, darcyVelocity
    
    def PVBtCurveAnaliticalWhiteDetailsPhi(self):

        analicalPoints = np.linspace(self.mininum_porosity, self.core_porosity, self.step_numbers)
        PVBtPoints = []
        intersticialVelocity = []
        iDa = []
        volumeToBt = []
        timeToBt = []
        wormholeVelocity = []
        darcyVelocity = []
        for p in analicalPoints:
            setup = PVBtSetup(
                self.acidtype,
                self.acid_concentration,
                self.core_diameter,
                self.core_length,
                p,
                self.rock_type,
                self.temperature,
                self.flowrate,
            )
            PVBtCalculator = PVBt(setup)
            PVBtPoints.append(PVBtCalculator.PoreVolumeTobreakthroughCalculator())
            intersticialVelocity.append(PVBtCalculator.InterticialVelocityCalculator())
            iDa.append(PVBtCalculator.InverseDamkholerCalculator())
            volumeToBt.append(PVBtCalculator.AcidVolumeToBtCalculator())
            timeToBt.append(PVBtCalculator.TimeToBtCalculator())
            wormholeVelocity.append(PVBtCalculator.WormholeVelocityCalculator())
            darcyVelocity.append(PVBtCalculator.DarcyVelocityCalculator())

        
        return PVBtPoints, analicalPoints, intersticialVelocity, iDa, volumeToBt, timeToBt, wormholeVelocity, darcyVelocity
    
    def PVBtCurveAnaliticalWhiteDetailsLength(self):

        analicalPoints = np.linspace(self.minimum_length, self.core_length, self.step_numbers)
        analitical = []
        PVBtPoints = []
        intersticialVelocity = []
        iDa = []
        volumeToBt = []
        timeToBt = []
        wormholeVelocity = []
        darcyVelocity = []
        for p in analicalPoints:
            setup = PVBtSetup(
                self.acidtype,
                self.acid_concentration,
                self.core_diameter,
                p,
                self.core_porosity,
                self.rock_type,
                self.temperature,
                self.flowrate,
            )
            PVBtCalculator = PVBt(setup)
            PVBtPoints.append(PVBtCalculator.PoreVolumeTobreakthroughCalculator())
            intersticialVelocity.append(PVBtCalculator.InterticialVelocityCalculator())
            iDa.append(PVBtCalculator.InverseDamkholerCalculator())
            volumeToBt.append(PVBtCalculator.AcidVolumeToBtCalculator())
            timeToBt.append(PVBtCalculator.TimeToBtCalculator())
            wormholeVelocity.append(PVBtCalculator.WormholeVelocityCalculator())
            darcyVelocity.append(PVBtCalculator.DarcyVelocityCalculator())
            analitical.append(p * 39.37)
        
        return PVBtPoints, analitical, intersticialVelocity, iDa, volumeToBt, timeToBt, wormholeVelocity, darcyVelocity
    
    def PVBtCurveAnaliticalWhiteDetailsDiameter(self):

        analicalPoints = np.linspace(self.minimum_diameter, self.core_diameter, self.step_numbers)
        analitical = []
        PVBtPoints = []
        intersticialVelocity = []
        iDa = []
        volumeToBt = []
        timeToBt = []
        wormholeVelocity = []
        darcyVelocity = []
        for p in analicalPoints:
            setup = PVBtSetup(
                self.acidtype,
                self.acid_concentration,
                p,
                self.core_length,
                self.core_porosity,
                self.rock_type,
                self.temperature,
                self.flowrate,
            )
            PVBtCalculator = PVBt(setup)
            PVBtPoints.append(PVBtCalculator.PoreVolumeTobreakthroughCalculator())
            intersticialVelocity.append(PVBtCalculator.InterticialVelocityCalculator())
            iDa.append(PVBtCalculator.InverseDamkholerCalculator())
            volumeToBt.append(PVBtCalculator.AcidVolumeToBtCalculator())
            timeToBt.append(PVBtCalculator.TimeToBtCalculator())
            wormholeVelocity.append(PVBtCalculator.WormholeVelocityCalculator())
            darcyVelocity.append(PVBtCalculator.DarcyVelocityCalculator())
            analitical.append(p * 39.37)
        
        return PVBtPoints, analitical, intersticialVelocity, iDa, volumeToBt, timeToBt, wormholeVelocity, darcyVelocity

    def PVBtCurveAnaliticalWhiteDetailsConcentration(self):

        analicalPoints = np.linspace(self.minimum_concentration, self.acid_concentration, self.step_numbers)
        PVBtPoints = []
        intersticialVelocity = []
        iDa = []
        volumeToBt = []
        timeToBt = []
        wormholeVelocity = []
        darcyVelocity = []
        for p in analicalPoints:
            setup = PVBtSetup(
                self.acidtype,
                p,
                self.core_diameter,
                self.core_length,
                self.core_porosity,
                self.rock_type,
                self.temperature,
                self.flowrate,
            )
            PVBtCalculator = PVBt(setup)
            PVBtPoints.append(PVBtCalculator.PoreVolumeTobreakthroughCalculator())
            intersticialVelocity.append(PVBtCalculator.InterticialVelocityCalculator())
            iDa.append(PVBtCalculator.InverseDamkholerCalculator())
            volumeToBt.append(PVBtCalculator.AcidVolumeToBtCalculator())
            timeToBt.append(PVBtCalculator.TimeToBtCalculator())
            wormholeVelocity.append(PVBtCalculator.WormholeVelocityCalculator())
            darcyVelocity.append(PVBtCalculator.DarcyVelocityCalculator())

        
        return PVBtPoints, analicalPoints, intersticialVelocity, iDa, volumeToBt, timeToBt, wormholeVelocity, darcyVelocity
    



