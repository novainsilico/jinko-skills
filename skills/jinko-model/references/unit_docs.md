---
title: "Unit usage"
---

## How and where are units used ? 

Units are defined for input components of a computational model, namely Parameters, Compartments and Species.

There are 4 distinct behaviors when it comes to dealing with units in a model. Those 4 behaviors are controlled by the `unitCheck` option in the options of your model.

1.  `unitCheck = NoUnitCheck`  
    Units are not used, and no dimension checking is performed. This is the default behavior upon uploading an SBML model.
2.  `unitCheck = UnitCheckWithNoUnitConversion`  
    Units are used and dimension checking is performed. Mathematical formulas are all evaluated numerically, and no implicit unit conversions are done. If you wish to perform dimension checking on an SBML model, we recommend that you use this mode, as it aligns with the specification stating that SBML does not define implicit unit conversions.
3.  `unitCheck = UnitCheckAndConvertAllSpeciesToExtentUnits` and `unitCheck = UnitCheckAndConvertOnlyReactantsAndProductsToExtentUnits`  
    When either of those two modes is chosen, **species** have a specific behavior with regards to units.  
      
    When using `unitCheck = UnitCheckAndConvertAllSpeciesToExtentUnits`, all species are converted to the extentUnits (**this is the default behavior for a new model in jinko**).  
      
    When using `unitCheck = UnitCheckAndConvertOnlyReactantsAndProductsToExtentUnit`, only the species used as a reactant or product of a reaction are converted.  
      
    However, in both cases, the species are reconverted back to their unit in the results - the `extentUnits` is only used for the resolution, therefore in the formulas that use these species. The unit of species is the same as the unit of the initial condition.   
      
    Contrary to `UnitCheckWithNoUnitConversion`, implicit conversions are carried out. For instance, consider the formula `p1 + p2` where `p1` is in **mol** and `p2` is in **mmol**. The formula is considered to be expressed in **mol** and is numerically evaluated as `p1 + 0.001*p2`.

The field `extentUnits` defaults to mol and can be changed to whatever unit, as long as your reaction rates are expressed in the dimension`[extentUnits/timeUnits]`. This means however that the unit of species should be convertible to `extentUnits`. For instance if species has unit "mol/L" and extentUnits="mol" then we use the compartment volume and convert the species to "mol". However, if "extentUnits=m^3" and the species has unit "mol", then this won't work. It only works if all the species to be converted to the extent units are already expressed in the extent units (this is the case for instance for some models that have everything expressed in "dimensionless") or in a unit that can be converted to the `extentUnits`.

All the other components, including species that are not used in any bioreaction, are kept in their defined units, both in the input, the plotted outputs and in the formulas. 

**For example**: I have   
`unitCheck = UnitCheckAndConvertOnlyReactantsAndProductsToExtentUnits, extentUnits = mol`  
`S1 = 0.3 mol/L    S2 = 0.1 g   P1 = 2 /s   P2 = 2 g   P3 = S2 + P2`  
`S2` is not used in a bioreaction, so `S2` is in grams and the dimension check of the formula works fine.  
`R1: S1 -> 2*S1, v = P1* S1`   
`S1` however will be converted to moles for its use in the formula in `R1`'s rate.

When running the simulation, I will get in my outputs `S1` in `mol/L`, `S2`, `P2` and `P3` in `g` and `P1` in `/s`. 

If I change `unitCheck` to `UniCheckAndConvertAllSpeciesToExtentUnits`, or if I add a new reaction `R2: S2 -> S1`, `S2` will be converted to the `[extentUnits]` (mol) and the formula for `P3` will no longer be correct. 

## **Semantics of units**

Units are divided into **base units** (meter, second, mole etc.) and **non-base units** (dimensionless, minute, hour etc.). 

A notable distinction from the International System of Units (SI) is that base units never have prefixes; so the base unit of mass is gram, not kilogram.

Let `u1`, `u2`, ... be the set of base units. Then the meaning of any unit is the expression `C * u1**p1 * u2**p2 * ...`, where `C` is real, `p1`, `p2` ... are integers, and `u1`, `u2` ... are the base units treated as abstract variables for the purpose of algebraic manipulations. Such an expression is called a **dimensional quantity**.

The interpretation of dimensional quantity (denoted as `[[unit]]`) is then straightforward:

*   `[[dimensionless]] = 1`.
*   `[[named_unit]]` is just named\_unit for base units; for derived units the interpretation follows those units' definitions, e.g. \[\[minute\]\] = 60 \* second.
*   `[[prefix, named_unit]] = C * [[named_unit]]`, where `C` is the numerical factor corresponding to that prefix. E.g. `[[kilo named_unit]] = 1000 * [[named_unit]]`.
*   `[[unit1, "*", unit2]] = [[unit1]] * [[unit2]]`.

### Examples

*   to define a molar mass, a unit that can be used is `unit = g / mmol`
*   a volume velocity can be expressed with `unit = mol * m**-3 * s**-1`

## Exhaustive list of units

Below is a list of all the units and prefixes that can be used in the platform.

**Base units**

*   meter = \[length\] = m = metre
*   second = \[time\] = s = sec
*   gram = \[mass\] = g
*   mole = \[substance\] = mol
*   degK = \[temperature\] = K = kelvin
*   ampere = \[current\] = A = amp
*   candela = \[luminosity\] = cd = candle
*   radian = \[\] = rad
*   bit = \[\]
*   count = \[\]
*   dimensionless = \[\]

**Length units**

*   angstrom = 1e-10 \* meter
*   inch = 2.54 \* centimeter = international\_inch = inches = international\_inches = in
*   foot = 12 \* inch = international\_foot = ft = feet = international\_foot = international\_feet
*   mile = 5280 \* foot = mi = international\_mile
*   yard = 3 \* feet = yd = international\_yard
*   mil = inch / 1000 = thou
*   parsec = 3.08568025e16 \* meter = pc
*   light\_year = speed\_of\_light \* julian\_year = ly = lightyear
*   astronomical\_unit = 149597870691 \* meter = au
*   nautical\_mile = 1.852e3 \* meter = nmi
*   printers\_point = 127 \* millimeter / 360 = point
*   printers\_pica = 12 \* printers\_point = pica
*   US\_survey\_foot = 1200 \* meter / 3937
*   US\_survey\_yard = 3 \* US\_survey\_foot
*   US\_survey\_mile = 5280 \* US\_survey\_foot = US\_statute\_mile
*   rod = 16.5 \* US\_survey\_foot = pole = perch
*   furlong = 660 \* US\_survey\_foot
*   fathom = 6 \* US\_survey\_foot
*   chain = 66 \* US\_survey\_foot
*   barleycorn = inch / 3
*   arpentlin = 191.835 \* feet
*   kayser = 1 / centimeter = wavenumber

**Area units**

*   are = 100 \* m\*\*2
*   barn = 1e-28 \* m \*\* 2 = b
*   cmil = 5.067075e-10 \* m \*\* 2 = circular\_mils
*   darcy = 9.869233e-13 \* m \*\* 2
*   acre = 4046.8564224 \* m \*\* 2 = international\_acre
*   US\_survey\_acre = 160 \* rod \*\* 2

**Volume units**

*   liter = 1e-3 \* m \*\* 3 = l = L = litre
*   cc = centimeter \*\* 3 = cubic\_centimeter
*   stere = meter \*\* 3
*   gross\_register\_ton = 100 \* foot \*\* 3 = register\_ton = GRT
*   acre\_foot = acre \* foot = acre\_feet
*   board\_foot = foot \*\* 2 \* inch = FBM
*   bushel = 2150.42 \* inch \*\* 3 = bu = US\_bushel
*   dry\_gallon = bushel / 8 = US\_dry\_gallon
*   dry\_quart = dry\_gallon / 4 = US\_dry\_quart
*   dry\_pint = dry\_quart / 2 = US\_dry\_pint
*   gallon = 231 \* inch \*\* 3 = liquid\_gallon = US\_liquid\_gallon
*   quart = gallon / 4 = liquid\_quart = US\_liquid\_quart
*   pint = quart / 2 = pt = liquid\_pint = US\_liquid\_pint
*   cup = pint / 2 = liquid\_cup = US\_liquid\_cup
*   gill = cup / 2 = liquid\_gill = US\_liquid\_gill
*   floz = gill / 4 = fluid\_ounce = US\_fluid\_ounce = US\_liquid\_ounce
*   imperial\_bushel = 36.36872 \* liter = UK\_bushel
*   imperial\_gallon = imperial\_bushel / 8 = UK\_gallon
*   imperial\_quart = imperial\_gallon / 4 = UK\_quart
*   imperial\_pint = imperial\_quart / 2 = UK\_pint
*   imperial\_cup = imperial\_pint / 2 = UK\_cup
*   imperial\_gill = imperial\_cup / 2 = UK\_gill
*   imperial\_floz = imperial\_gill / 5 = UK\_fluid\_ounce = imperial\_fluid\_ounce
*   barrel = 42 \* gallon = bbl
*   tablespoon = floz / 2 = tbsp = Tbsp = Tblsp = tblsp = tbs = Tbl
*   teaspoon = tablespoon / 3 = tsp
*   peck = bushel / 4 = pk
*   fluid\_dram = floz / 8 = fldr = fluidram
*   firkin = barrel / 4

**Time Units**

*   minute = 60 \* second = min
*   hour = 60 \* minute = h = hr
*   day = 24 \* hour
*   week = 7 \* day
*   fortnight = 2 \* week
*   year = 31556925.9747 \* second
*   month = year/12
*   shake = 1e-8 \* second
*   sidereal\_day = day / 1.00273790935079524
*   sidereal\_hour = sidereal\_day/24
*   sidereal\_minute = sidereal\_hour/60
*   sidereal\_second =sidereal\_minute/60
*   sidereal\_year = 366.25636042 \* sidereal\_day
*   sidereal\_month = 27.321661 \* sidereal\_day
*   tropical\_month = 27.321661 \* day
*   synodic\_month = 29.530589 \* day = lunar\_month
*   common\_year = 365 \* day
*   leap\_year = 366 \* day
*   julian\_year = 365.25 \* day
*   gregorian\_year = 365.2425 \* day
*   millenium = 1000 \* year = millenia = milenia = milenium
*   eon = 1e9 \* year
*   work\_year = 2056 \* hour
*   work\_month = work\_year/12

**Frequency units**

*   hertz = 1 / second = Hz = rps
*   revolutions\_per\_minute = revolution / minute = rpm
*   counts\_per\_second = count / second = cps

**Velocity units**

*   knot = nautical\_mile / hour = kt = knot\_international = international\_knot = nautical\_miles\_per\_hour
*   mph = mile / hour = MPH
*   kph = kilometer / hour = KPH

**Mass units**

*   ounce = 28.349523125 \* gram = oz = avoirdupois\_ounce
*   dram = oz / 16 = dr = avoirdupois\_dram
*   pound = 0.45359237 \* kilogram = lb = avoirdupois\_pound
*   stone = 14 \* lb = st
*   carat = 200 \* milligram
*   grain = 64.79891 \* milligram = gr
*   long\_hundredweight = 112 \* lb
*   short\_hundredweight = 100 \* lb
*   metric\_ton = 1000 \* kilogram = t = tonne
*   pennyweight = 24 \* gram = dwt
*   slug = 14.59390 \* kilogram
*   troy\_ounce = 480 \* gram = toz = apounce = apothecary\_ounce
*   troy\_pound = 12 \* toz = tlb = appound = apothecary\_pound
*   drachm = 60 \* gram = apdram = apothecary\_dram
*   atomic\_mass\_unit = 1.660538782e-27 \* kilogram = u = amu = dalton = Da
*   scruple = 20 \* gram
*   bag = 94 \* lb
*   ton = 2000 \* lb = short\_ton

**Force units**

*   newton = kilogram \* meter / second \*\* 2 = N
*   dyne = gram \* centimeter / second \*\* 2 = dyn
*   force\_kilogram = g\_0 \* kilogram = kgf = kilogram\_force = pond
*   force\_gram = g\_0 \* gram = gf = gram\_force
*   force\_ounce = g\_0 \* ounce = ozf = ounce\_force
*   force\_pound = g\_0 \* lb = lbf = pound\_force
*   force\_ton = 2000 \* force\_pound = ton\_force
*   poundal = lb \* feet / second \*\* 2 = pdl
*   kip = 1000\*lbf

**Energy units**

*   joule = newton \* meter = J
*   erg = dyne \* centimeter
*   btu = 1.05505585262e3 \* joule = Btu = BTU = british\_thermal\_unit
*   eV = 1.60217653e-19 \* J = electron\_volt
*   thm = 100000 \* BTU = therm = EC\_therm
*   cal = 4.184 \* joule = calorie = thermochemical\_calorie
*   international\_steam\_table\_calorie = 4.1868 \* joule
*   ton\_TNT = 4.184e9 \* joule = tTNT
*   US\_therm = 1.054804e8 \* joule
*   E\_h = 4.35974394e-18 \* joule = hartree = hartree\_energy
*   watt\_hour = watt \* hour = Wh = watthour

**Pressure units**

*   Hg = gravity \* 13.59510 \* gram / centimeter \*\* 3 = mercury = conventional\_mercury
*   mercury\_60F = gravity \* 13.5568 \* gram / centimeter \*\* 3
*   H2O = gravity \* 1000 \* kilogram / meter \*\* 3 = h2o = water = conventional\_water
*   water\_4C = gravity \* 999.972 \* kilogram / meter \*\* 3 = water\_39F
*   water\_60F = gravity \* 999.001 \* kilogram / m \*\* 3
*   pascal = newton / meter \*\* 2 = Pa
*   bar = 100000 \* pascal
*   atmosphere = 101325 \* pascal = atm = standard\_atmosphere
*   technical\_atmosphere = kilogram \* gravity / centimeter \*\* 2 = at
*   torr = atm / 760
*   psi = pound \* gravity / inch \*\* 2 = pound\_force\_per\_square\_inch
*   ksi = kip / inch \*\* 2 = kip\_per\_square\_inch
*   barye = 0.1 \* newton / meter \*\* 2 = barie = barad = barrie = baryd = Ba
*   mmHg = millimeter \* Hg = mm\_Hg = millimeter\_Hg = millimeter\_Hg\_0C
*   cmHg = centimeter \* Hg = cm\_Hg = centimeter\_Hg
*   inHg = inch \* Hg = in\_Hg = inch\_Hg = inch\_Hg\_32F
*   inch\_Hg\_60F = inch \* mercury\_60F
*   inch\_H2O\_39F = inch \* water\_39F
*   inch\_H2O\_60F = inch \* water\_60F
*   footH2O = ft \* water
*   cmH2O = centimeter \* water
*   foot\_H2O = ft \* water = ftH2O
*   standard\_liter\_per\_minute = 1.68875 \* Pa \* m \*\* 3 / s = slpm = slm
*   Velocity units

**Viscosity units**

*   poise = 1e-1 \* Pa \* second = P
*   stokes = 1e-4 \* meter \*\* 2 / second = St
*   rhe = 10 / (Pa \* s)

**Power units**

*   watt = joule / second = W = volt\_ampere = VA
*   horsepower = 33000 \* ft \* lbf / min = hp = UK\_horsepower = British\_horsepower
*   boiler\_horsepower = 33475 \* btu / hour
*   metric\_horsepower = 75 \* force\_kilogram \* meter / second
*   electric\_horsepower = 746 \* watt
*   hydraulic\_horsepower = 550 \* feet \* lbf / second
*   refrigeration\_ton = 12000 \* btu / hour = ton\_of\_refrigeration

**Substance units**

*   avogadro = 6.02214076e23
*   substance\_count = 1 / avogadro \* mole = substcount = scount
*   katal = mole / second = kat

**Electromagnetic units**

*   esu = 1 \* erg\*\*0.5 \* centimeter\*\*0.5 = statcoulombs = statC = franklin = Fr
*   esu\_per\_second = 1 \* esu / second = statampere
*   ampere\_turn = 1 \* A
*   gilbert = 10 / (4 \* pi ) \* ampere\_turn = G
*   coulomb = ampere \* second = C
*   volt = joule / coulomb = V
*   farad = coulomb / volt = F
*   ohm = volt / ampere
*   siemens = ampere / volt = S = mho
*   weber = volt \* second = Wb
*   tesla = weber / meter \*\* 2 = T
*   henry = weber / ampere = H
*   elementary\_charge = 1.602176487e-19 \* coulomb = e
*   chemical\_faraday = 9.64957e4 \* coulomb
*   physical\_faraday = 9.65219e4 \* coulomb
*   faraday = 96485.3399 \* coulomb = C12\_faraday
*   gamma = 1e-9 \* tesla
*   gauss = 1e-4 \* tesla
*   maxwell = 1e-8 \* weber = mx
*   oersted = 1000 / (4 \* pi) \* A / m = Oe
*   statfarad = 1.112650e-12 \* farad = statF = stF
*   stathenry = 8.987554e11 \* henry = statH = stH
*   statmho = 1.112650e-12 \* siemens = statS = stS
*   statohm = 8.987554e11 \* ohm
*   statvolt = 2.997925e2 \* volt = statV = stV
*   unit\_pole = 1.256637e-7 \* weber

**Luminosity units**

*   lumen = candela \* steradian = lm
*   lux = lumen / meter \*\*2 = lx

**Angle Units**

*   turn = 2 \* pi \* radian = revolution = cycle = circle
*   degree = pi / 180 \* radian = deg = arcdeg = arcdegree = angular\_degree
*   arcminute = arcdeg / 60 = arcmin = arc\_minute = angular\_minute
*   arcsecond = arcmin / 60 = arcsec = arc\_second = angular\_second
*   steradian = radian \*\* 2 = sr

**Information units**

*   byte = 8 \* bit = Bo = octet
*   baud = bit / second = Bd = bps

**Textile units**

*   denier = gram / (9000 \* meter)
*   tex = gram/ (1000 \* meter)
*   dtex = decitex

**Nuclear units**

*   Bq = Hz = becquerel
*   curie = 3.7e10 \* Bq = Ci
*   rutherford = 1e6\*Bq = rd = Rd
*   Gy = joule / kilogram = gray = Sv = sievert
*   rem = 1e-2 \* sievert
*   rads = 1e-2 \* gray
*   roentgen = 2.58e-4 \* coulomb / kilogram = R

**Constants**

*   pi = 3.141592653589793
*   gstandard\_gravity = 9.806650 \* meter / second \*\* 2 = g\_0 = g\_n = gravity
*   speed\_of\_light = 299792458 \* meter / second = c

**Decimal prefixes**

*   yocto- = 1e-24 = y-
*   zepto- = 1e-21 = z-
*   atto- = 1e-18 = a-
*   femto- = 1e-15 = f-
*   pico- = 1e-12 = p-
*   nano- = 1e-9 = n-
*   micro- = 1e-6 = u-
*   milli- = 1e-3 = m-
*   centi- = 1e-2 = c-
*   deci- = 1e-1 = d-
*   deca- = 1e+1 = da-
*   hecto- = 1e2 = h-
*   kilo- = 1e3 = k-
*   mega- = 1e6 = M-
*   giga- = 1e9 = G-
*   tera- = 1e12 = T-
*   peta- = 1e15 = P-
*   exa- = 1e18 = E-
*   zetta- = 1e21 = Z-
*   yotta- = 1e24 = Y-

**Binary prefixes**

*   kibi- = 2\*\*10 = Ki-
*   mebi- = 2\*\*20 = Mi-
*   gibi- = 2\*\*30 = Gi-
*   tebi- = 2\*\*40 = Ti-
*   pebi- = 2\*\*50 = Pi-
*   exbi- = 2\*\*60 = Ei-
*   zebi- = 2\*\*70 = Zi-
*   yobi- = 2\*\*80 = Yi-
