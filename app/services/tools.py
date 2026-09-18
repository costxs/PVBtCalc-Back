from app.services.PVBTfunc import AcidType, PVBtMaster
from app.schemas import PVBtInputPoint, AnalicalInput
from typing import List
def getparam(data: PVBtInputPoint):

    master = PVBtMaster(
        AcidType.getAcidTypeByStr(data.acid_type),
        data.acid_concentration,
        data.core_diameter,
        data.core_length,
        data.core_porosity,
        data.rock_type,
        data.temperature,
        data.flowrate
    )

    setup = master.getSetup()

    return{
        "ro":setup.acid_density,
        "X":setup.acid_volumetric_dissolving_power100,
        "x":setup.acid_volumetric_dissolving_power,
        "n":setup.acidsetup.n,
        "a":setup.acidsetup.a,
        "b":setup.acidsetup.b,
        "k0":setup.acidsetup.k0,
    }

def getOptPVBt(PVBt:List[float]):
    return min(PVBt)


from app.services.PVBTradialFunc import PVBtRadial, RadialGeometry, target_to_lambda, diffusion_coefficient, acid_volumetric_dissolving_power100, FT_TO_M, IN_TO_M
from app.services.PVBTfunc import ROCKFLOWFRACTION
from app.services.units import flowrate_to_m3s
import numpy as np

def get_correct_param(data: AnalicalInput):
    # Map parameter names to object attributes
    attr_map = {
        'temperature': 'temperature',
        'core length': 'payzone_thickness_ft' if data.flow_regime == 'radial' else 'core_length',
        'core porosity': 'core_porosity',
        'core diameter': 'wellbore_radius_in' if data.flow_regime == 'radial' else 'core_diameter',
        'acid concentration': 'acid_concentration'
    }
    
    sweep_param = data.analitical_param
    attr_name = attr_map.get(sweep_param, sweep_param)
    
    current_val = getattr(data, attr_name)
    start_val = data.minimum_analitical
    steps = data.step_numbers
    
    sweep_values = np.linspace(start_val, current_val, steps)
    
    pvbtpoints = []
    volumetobt = []
    analiticalpoints = []
    insterticialvelocity = []
    ida = []
    timetobt = []
    wormholevelocity = []
    darcyvelocity = []
    
    acid_cls = AcidType.getAcidTypeByStr(data.acid_type)
    q_m3s = flowrate_to_m3s(data.flowrate, "bbl_min") if data.flow_regime == 'radial' else None

    for val in sweep_values:
        setattr(data, attr_name, val)
        
        # O backend formata o eixo X apropriadamente.
        if sweep_param == 'temperature' and data.flow_regime != 'radial':
            # PVBtCurveAnaliticalWhiteDetailsTemp subtraía 273.15, 
            # mas vamos manter o valor para garantir conformidade
            analiticalpoints.append(val)
        elif sweep_param == 'core length' and data.flow_regime != 'radial':
            analiticalpoints.append(val * 39.37) # mantendo compatibilidade de polegada para linear
        elif sweep_param == 'core diameter' and data.flow_regime != 'radial':
            analiticalpoints.append(val * 39.37)
        else:
            analiticalpoints.append(val)

        if data.flow_regime == 'radial':
            conc = data.acid_concentration
            temp = data.temperature
            phi = data.core_porosity
            rw_in = data.wellbore_radius_in
            h_ft = data.payzone_thickness_ft
            
            acidsetup = acid_cls(conc)
            geo = RadialGeometry(r_w_m=rw_in * IN_TO_M, h_o_m=h_ft * FT_TO_M, porosity=phi)
            Dm = diffusion_coefficient(temp, conc)
            X = acid_volumetric_dissolving_power100(conc, temp - 273.15)
            f = ROCKFLOWFRACTION.get(data.rock_type, 1.0)

            modelo_radial = PVBtRadial(
                geo,
                a=acidsetup.a,
                b=acidsetup.b,
                n=acidsetup.n,
                k0=acidsetup.k0,
                Dm=Dm,
                C_Ao=conc,
                X=X,
                flowrate_m3s=q_m3s,
                f=f,
            )
            
            target_val = data.target if getattr(data, 'target', None) is not None else (data.targets[0] if getattr(data, 'targets', None) and len(data.targets) > 0 else 5.0)
            target_m = getattr(data, 'target_mode', 'length')
            lam = target_to_lambda(target_val, target_m, geo.beta, geo.L)
            
            wv = modelo_radial.v_o * modelo_radial.omega(0.0)
            damkholer = modelo_radial.keff * geo.L / wv
            expoente = modelo_radial.K * modelo_radial.alpha(lam)
            is_clipped = expoente > PVBtRadial.LIMITE_EXP
            volume = None if is_clipped else (modelo_radial.acid_volume(lam) * 264.172) / h_ft
            
            volumetobt.append(volume)
            pvbtpoints.append(None)
            insterticialvelocity.append(modelo_radial.v_o / geo.porosity)
            ida.append(1.0 / damkholer)
            timetobt.append(None if is_clipped else modelo_radial.time_to_breakthrough_s(lam))
            wormholevelocity.append(wv)
            darcyvelocity.append(modelo_radial.v_o)
            
        else:
            modelo_linear = PVBtMaster(
                acidtype=acid_cls,
                acid_concentration=data.acid_concentration,
                core_diameter=data.core_diameter,
                core_length=data.core_length,
                core_porosity=data.core_porosity,
                rock_type=data.rock_type,
                temperature=data.temperature,
                flowrate=data.flowrate,
            )
            
            pvbt, _, inter_vel, id_val, vol_bt, time_bt, worm_vel, darcy_vel = modelo_linear.PVBtPointCalculatorWithDetails()
            
            pvbtpoints.append(pvbt)
            volumetobt.append(None)
            insterticialvelocity.append(inter_vel)
            ida.append(id_val)
            timetobt.append(time_bt)
            wormholevelocity.append(worm_vel)
            darcyvelocity.append(darcy_vel)

    return {
        "analyzed": sweep_param,
        "pvbtpoints": pvbtpoints,
        "analiticalpoints": analiticalpoints,
        "insterticialvelocity": insterticialvelocity,
        "ida": ida,
        "volumetobt": volumetobt,
        "timetobt": timetobt,
        "wormholevelocity": wormholevelocity,
        "darcyvelocity": darcyvelocity
    }

def generate_skin_evolution(data: AnalicalInput, flowrates_to_compare: List[float]):
    # Note: data could be SkinEvolutionInput, but we can reuse AnalicalInput structure
    import math
    from app.services.PVBTfunc import AcidType
    
    acid_cls = AcidType.getAcidTypeByStr(data.acid_type)
    conc = data.acid_concentration
    temp = data.temperature_k
    phi = data.core_porosity
    rw_in = data.wellbore_radius_in
    h_ft = data.payzone_thickness_ft
    
    acidsetup = acid_cls(conc)
    geo = RadialGeometry(r_w_m=rw_in * IN_TO_M, h_o_m=h_ft * FT_TO_M, porosity=phi)
    Dm = diffusion_coefficient(temp, conc)
    X = acid_volumetric_dissolving_power100(conc, temp - 273.15)
    f = ROCKFLOWFRACTION.get(data.rock_type, 1.0)

    r_w_ft = data.wellbore_radius_in / 12.0
    
    # Varredura do comprimento do wormhole (0.1 a 20 ft) - 50 pontos
    comprimentos_ft = np.linspace(0.1, 20.0, 50)
    
    resultados_por_vazao = {}
    M3_PER_M_TO_GAL_PER_FT = 264.172 * 0.3048

    for q in flowrates_to_compare:
        q_m3s = flowrate_to_m3s(q, "bbl_min")
        
        modelo_radial = PVBtRadial(
            geo,
            a=acidsetup.a,
            b=acidsetup.b,
            n=acidsetup.n,
            k0=acidsetup.k0,
            Dm=Dm,
            C_Ao=conc,
            X=X,
            flowrate_m3s=q_m3s,
            f=f,
        )

        curva_q = []
        for l_ft in comprimentos_ft:
            # Converte l_ft para lambda adimensional 
            # (L = 1.0 m no modelo PVBtRadial padrao, que e 3.28084 ft)
            L_char_ft = geo.L * 3.28084 
            lam = l_ft / L_char_ft
            
            # Calcula o Volume de acido usando a Eq 42. Retorna m^3/m. Multiplica para gal/ft.
            # is_clipped check is necessary since lam can be large.
            expoente = modelo_radial.K * modelo_radial.alpha(lam)
            if expoente > PVBtRadial.LIMITE_EXP:
                v_acid_gal_ft = None
            else:
                v_acid_m3 = modelo_radial.V_acid(lam)
                print(f"Area Ao: {modelo_radial.g.A_o}")
                print(f"Velocidade vo: {modelo_radial.v_o}")
                print(f"Constante K: {modelo_radial.K}")
                print(f"Volume m3: {v_acid_m3}")
                v_acid_gal_ft = (v_acid_m3 * 264.172) / h_ft
            
            # Calcula o Skin equivalente
            skin = -math.log((r_w_ft + l_ft) / r_w_ft)

            # l_ft (Fase 8): a tabela do frontend precisa do comprimento por
            # ponto -- sem isso, so daria pra reconstruir invertendo a formula
            # do skin acima (l = r_w*(exp(-skin)-1)), duplicando-a no front.
            curva_q.append({"x": v_acid_gal_ft, "y": skin, "l_ft": l_ft})
            
        resultados_por_vazao[str(q)] = curva_q

    return resultados_por_vazao

