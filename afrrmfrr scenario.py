import pandas as pd  # Dataframes
from pulp import *  # Simplex
import uuid  # Unique ID in output file
import json  # pretty printing output dict
import time
start_time = time.time()

demand_df = pd.read_excel(
    r"C:\Users\csika\Desktop\2021_full_imbalance_20221201.xlsx")

targetDemand_with_nan = demand_df['SZUMMA'].tolist()
targetDemandList = [x for x in targetDemand_with_nan if str(x) != 'nan']

df = pd.read_csv(r"C:\Users\csika\Desktop\FULL_merged_ajanlatok-20210101-20210102.csv",
    sep=';', skipinitialspace=True)

overallCounter = 0

output_dict = {"Unique ID": [],
               "Időpont": [],
               "Kereslet (MW)": [],
               "Irány": [],
               "Kínálat (HUF)": [],
               "Optimális eredmény?": [],
               "Piac": [],
               "Volumen": [],
               "Maradék Volumen": [],
               "Ár": []}

while overallCounter < 20:

    targetDemand = targetDemandList[overallCounter]
    # print(targetDemand)

    quarterCategory = int(demand_df.at[overallCounter, 'Időpont'][14:16])  # 0 v. bármi más
    aktualisDatum = demand_df.at[overallCounter, 'Időpont'][:10]
    supplyProductStartHour = int(demand_df.at[overallCounter, 'Időpont'][11:13])
    supplyProductEndHour = supplyProductStartHour + 1

    if quarterCategory != 0:
        if len(str(supplyProductStartHour)) == 1:
            supplyProductTime = "0{}:00-0{}:00".format(supplyProductStartHour, supplyProductEndHour)
            # print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)
            if supplyProductStartHour == 9:
                supplyProductTime = "0{}:00-{}:00".format(supplyProductStartHour, supplyProductEndHour)
                # print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)
        else:
            if supplyProductStartHour == 23:
                supplyProductTime = "23:00-00:00".format(supplyProductStartHour - 1, supplyProductStartHour)
                # print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)
            else:
                supplyProductTime = "{}:00-{}:00".format(supplyProductStartHour, supplyProductEndHour)
                # print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)
    else:
        if len(str(supplyProductStartHour)) == 1:
            supplyProductTime = "0{}:00-0{}:00".format(supplyProductStartHour - 1, supplyProductStartHour)
            print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)
            if supplyProductStartHour == 0:
                supplyProductTime = "00:00-01:00"
                print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)
            if supplyProductStartHour == 9:
                supplyProductTime = "0{}:00-0{}:00".format(supplyProductStartHour - 1, supplyProductStartHour)
                print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)
                print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)
        else:
            if supplyProductStartHour == 10:
                supplyProductTime = "0{}:00-{}:00".format(supplyProductStartHour - 1, supplyProductStartHour)
                print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)
            else:
                supplyProductTime = "{}:00-{}:00".format(supplyProductStartHour - 1, supplyProductStartHour)
                print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)

    if targetDemand > 0:
        problemType = LpMinimize
        supplyDirection = "Pozitiv / Positive"
    else:
        targetDemand = targetDemand * -1
        problemType = LpMaximize
        supplyDirection = "Negativ / Negative"

    afrr_df = df[(df['Piac / Market'] == 'aFRR / aFRR')
        & (df['Irany / Direction'] == supplyDirection)
        & (df['Datum / Date'] == aktualisDatum)
        & (df['Termek / Product'] == supplyProductTime)]

    afrr_ids = afrr_df.index.astype(str).tolist()
    afrr_df.insert(loc=0, column='row_id', value=afrr_ids)
    afrr_df['Piac / Market'] = afrr_df['Piac / Market'] + afrr_df['row_id']
    afrrVendors = afrr_df['Piac / Market'].tolist()

    mfrr_df = df[(df['Piac / Market'] == 'mFRR es RR / mFRR and RR')
        & (df['Irany / Direction'] == supplyDirection)
        & (df['Datum / Date'] == aktualisDatum)
        & (df['Termek / Product'] == supplyProductTime)]

    mfrr_ids = mfrr_df.index.astype(str).tolist()
    mfrr_df.insert(loc=0, column='row_id', value=mfrr_ids)
    mfrr_df['Piac / Market'] = mfrr_df['Piac / Market'] + mfrr_df['row_id']
    mfrrVendors = mfrr_df['Piac / Market'].tolist()

    afrrVendorCostsList = afrr_df['Energia ar / Energy Price [HUF/MWh]'].tolist()
    mfrrVendorCostsList = mfrr_df['Energia ar / Energy Price [HUF/MWh]'].tolist()

    afrrVendorCosts = dict(zip(afrrVendors, afrrVendorCostsList))
    mfrrVendorCosts = dict(zip(mfrrVendors, mfrrVendorCostsList))

    afrrVendorVolumeList = afrr_df['Felajanlott mennyiseg / Offered Capacity [MW]'].tolist()
    mfrrVendorVolumeList = mfrr_df['Felajanlott mennyiseg / Offered Capacity [MW]'].tolist()

    afrrVendorVolumes = dict(zip(afrrVendors, afrrVendorVolumeList))
    mfrrVendorVolumes = dict(zip(mfrrVendors, mfrrVendorVolumeList))

    prob = LpProblem("The MAVIR MVP Optimization Problem", problemType)

    afrrVendorVars = LpVariable.dicts("afrrVendor", afrrVendors, 0)
    mfrrVendorVars = LpVariable.dicts("mfrrVendor", mfrrVendors, 0)
    useMfrr = LpVariable.dicts("useMfrr", mfrrVendors, 0, 1, LpBinary)

    # The objective function is added to 'prob' first
    prob += (
        lpSum([afrrVendorCosts[i] * afrrVendorVars[i] for i in afrrVendors]) + lpSum(
            [mfrrVendorCosts[i] * mfrrVendorVars[i] for i in mfrrVendors]),
        "Optimal Cost to Fill Supply",
    )
    # The  constraints are added to 'prob'
    prob += (
        lpSum(afrrVendorVars[i] for i in afrrVendors) + lpSum(mfrrVendorVars[i] for i in mfrrVendors)) \
        == targetDemand, "Demand"

    for i in afrrVendors:
        prob += afrrVendorVars[i] <= afrrVendorVolumes[i]

    for j in mfrrVendors:
        prob += mfrrVendorVars[j] == mfrrVendorVolumes[j] * useMfrr[j]

    try:
        prob.solve()
    except:
        output_dict["Unique ID"].append(str(uuid.uuid4()))
        output_dict["Időpont"].append(demand_df.at[overallCounter, 'Időpont'])
        output_dict["Kereslet (MW)"].append(targetDemand)
        output_dict["Irány"].append(supplyDirection)
        output_dict["Kínálat (HUF)"].append("ERROR")
        output_dict["Optimális eredmény?"].append("ERROR")
        output_dict["Piac"].append("ERROR")
        output_dict["Volumen"].append("ERROR")
        output_dict["Maradék Volumen"].append("ERROR")
        output_dict['Ár'].append("ERROR")
        overallCounter += 1

    # print("Status:", LpStatus[prob.status])

    for v in prob.variables():
        if v.varValue > 0:
            if v.name[0] != 'u':
                print(v.name, "=", v.varValue)
                output_dict["Unique ID"].append(str(uuid.uuid4()))
                output_dict["Időpont"].append(demand_df.at[overallCounter, 'Időpont'])
                output_dict["Kereslet (MW)"].append(targetDemand)
                output_dict["Irány"].append(supplyDirection)
                output_dict["Kínálat (HUF)"].append(value(prob.objective))
                output_dict["Optimális eredmény?"].append(LpStatus[prob.status])
                output_dict["Piac"].append(v.name)
                output_dict["Volumen"].append(v.varValue)
                if v.name[0:1] == 'a':
                    output_dict["Maradék Volumen"].append(
                        afrrVendorVolumes['aFRR / aFRR{}'.format(v.name[v.name.index("___") + 7:])] - v.varValue)
                    output_dict['Ár'].append(
                        afrrVendorCosts['aFRR / aFRR{}'.format(v.name[v.name.index("___") + 7:])] * v.varValue)
                else:
                    output_dict["Maradék Volumen"].append(
                        mfrrVendorVolumes['mFRR es RR / mFRR and RR{}'.format(v.name[v.name.index("___") + 14:])] - v.varValue)
                    output_dict['Ár'].append(
                        mfrrVendorCosts['mFRR es RR / mFRR and RR{}'.format(v.name[v.name.index("___") + 14:])] * v.varValue)

    if supplyProductStartHour == 23:
        print(demand_df.at[overallCounter, 'Időpont'], supplyProductTime)
    overallCounter += 1

print("Done iterating!")
print(json.dumps(output_dict, indent=2))
output_df = pd.DataFrame(output_dict).to_excel(
'MAVIR_PSGA_simplex_output_{}.xlsx'.format(pd.datetime.today().strftime('%Y%m%d-%H%M%S')))
print("Done exporting!")
print("--- %s seconds ---" % (time.time() - start_time))