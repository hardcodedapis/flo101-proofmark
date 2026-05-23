from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from math import exp
from typing import Any

from .actions import recommend_for_pcm
from .schema import InputError


REVIEW_GAPS = [1, 3, 7, 11, 15]

JEE_HIGH_YIELD = {
    "Physics": {
        "Modern Physics",
        "Current Electricity",
        "Electrostatics",
        "Ray Optics and Optical Instruments",
        "Heat and Thermodynamics",
        "Rotational Motion",
        "Magnetism and Electromagnetic Induction",
    },
    "Chemistry": {
        "Coordination Compounds",
        "Chemical Bonding and Molecular Structure",
        "Equilibrium",
        "Electrochemistry",
        "Organic Chemistry: Basic Principles",
        "Thermodynamics",
        "The d- and f-Block Elements",
    },
    "Mathematics": {
        "Limits and Derivatives",
        "Applications of Derivatives",
        "Integrals",
        "Matrices",
        "Determinants",
        "Three Dimensional Geometry",
        "Vector Algebra",
        "Probability",
        "Straight Lines",
        "Conic Sections",
        "Complex Numbers and Quadratic Equations",
    },
}

QUESTION_BANK: list[dict[str, Any]] = [
    {
        "id": "phy-stoich-limiting-mcq",
        "type": "mcq",
        "domain": "Physical Chemistry",
        "class_level": "11",
        "chapter": "Some Basic Concepts of Chemistry",
        "subtopic": "Limiting reagent",
        "subparts": ["mole ratio", "limiting reagent", "yield prediction"],
        "difficulty": "medium",
        "prompt": "2 mol H2 reacts with 1 mol O2 to form water. Which reactant limits the reaction?",
        "options": [
            {"id": "A", "text": "H2"},
            {"id": "B", "text": "O2"},
            {"id": "C", "text": "Both are exactly consumed"},
            {"id": "D", "text": "Neither; water limits the reaction"},
        ],
        "answer": "C",
        "explanation": "The balanced equation is 2H2 + O2 -> 2H2O, so 2 mol H2 exactly reacts with 1 mol O2.",
    },
    {
        "id": "phy-atomic-debroglie-written",
        "type": "written",
        "domain": "Physical Chemistry",
        "class_level": "11",
        "chapter": "Structure of Atom",
        "subtopic": "de Broglie wavelength",
        "subparts": ["lambda = h/mv", "inverse relation", "particle speed"],
        "difficulty": "medium",
        "prompt": "Explain how de Broglie wavelength changes when the speed of an electron increases.",
        "keywords": ["wavelength", "lambda", "h/mv", "inversely", "momentum", "decreases"],
        "explanation": "de Broglie wavelength is inversely proportional to momentum; for an electron, higher speed means higher momentum and shorter wavelength.",
    },
    {
        "id": "phy-equilibrium-lechatelier-written",
        "type": "written",
        "domain": "Physical Chemistry",
        "class_level": "11",
        "chapter": "Equilibrium",
        "subtopic": "Le Chatelier principle",
        "subparts": ["stress response", "pressure shift", "moles of gas"],
        "difficulty": "medium",
        "prompt": "For N2(g) + 3H2(g) <=> 2NH3(g), explain the effect of increasing pressure.",
        "keywords": ["pressure", "fewer moles", "right", "ammonia", "le chatelier", "4 to 2"],
        "explanation": "Increasing pressure shifts equilibrium toward the side with fewer gaseous moles, so it favors ammonia formation.",
    },
    {
        "id": "phy-electro-nernst-mcq",
        "type": "mcq",
        "domain": "Physical Chemistry",
        "class_level": "12",
        "chapter": "Electrochemistry",
        "subtopic": "Nernst equation",
        "subparts": ["cell potential", "reaction quotient", "concentration dependence"],
        "difficulty": "hard",
        "prompt": "In the Nernst equation, increasing reaction quotient Q generally does what to Ecell?",
        "options": [
            {"id": "A", "text": "Increases Ecell"},
            {"id": "B", "text": "Decreases Ecell"},
            {"id": "C", "text": "Makes Ecell independent of concentration"},
            {"id": "D", "text": "Always makes Ecell zero"},
        ],
        "answer": "B",
        "explanation": "Ecell = E°cell - (RT/nF) ln Q, so increasing Q lowers Ecell.",
    },
    {
        "id": "phy-kinetics-order-written",
        "type": "written",
        "domain": "Physical Chemistry",
        "class_level": "12",
        "chapter": "Chemical Kinetics",
        "subtopic": "Order of reaction",
        "subparts": ["rate law", "experimental determination", "sum of powers"],
        "difficulty": "medium",
        "prompt": "What does order of reaction mean, and why is it not obtained from the balanced equation?",
        "keywords": ["rate law", "sum", "powers", "concentration", "experiment", "not stoichiometric"],
        "explanation": "Order is the sum of powers of concentration terms in the experimentally determined rate law.",
    },
    {
        "id": "phy-solutions-raoult-mcq",
        "type": "mcq",
        "domain": "Physical Chemistry",
        "class_level": "12",
        "chapter": "Solutions",
        "subtopic": "Raoult law",
        "subparts": ["vapour pressure", "mole fraction", "ideal solution"],
        "difficulty": "medium",
        "prompt": "For an ideal solution, partial vapour pressure of a component is proportional to its:",
        "options": [
            {"id": "A", "text": "molar mass"},
            {"id": "B", "text": "mole fraction"},
            {"id": "C", "text": "boiling point"},
            {"id": "D", "text": "density"},
        ],
        "answer": "B",
        "explanation": "Raoult's law states pA = xA pA°.",
    },
    {
        "id": "org-goc-acidity-mcq",
        "type": "mcq",
        "domain": "Organic Chemistry",
        "class_level": "11",
        "chapter": "Organic Chemistry: Basic Principles",
        "subtopic": "Inductive effect and acidity",
        "subparts": ["-I effect", "conjugate base stability", "acid strength"],
        "difficulty": "medium",
        "prompt": "Which compound is generally more acidic?",
        "options": [
            {"id": "A", "text": "CH3COOH"},
            {"id": "B", "text": "ClCH2COOH"},
            {"id": "C", "text": "CH3CH2OH"},
            {"id": "D", "text": "CH4"},
        ],
        "answer": "B",
        "explanation": "The -I effect of chlorine stabilizes the conjugate base, increasing acidity.",
    },
    {
        "id": "org-isomerism-chiral-mcq",
        "type": "mcq",
        "domain": "Organic Chemistry",
        "class_level": "11",
        "chapter": "Organic Chemistry: Basic Principles",
        "subtopic": "Optical isomerism",
        "subparts": ["chiral carbon", "four different groups", "optical activity"],
        "difficulty": "medium",
        "prompt": "A carbon atom is chiral when it is attached to:",
        "options": [
            {"id": "A", "text": "two identical groups"},
            {"id": "B", "text": "four different groups"},
            {"id": "C", "text": "only hydrogen atoms"},
            {"id": "D", "text": "a double bond and two groups"},
        ],
        "answer": "B",
        "explanation": "A tetrahedral carbon with four different groups is chiral.",
    },
    {
        "id": "org-hydrocarbon-markovnikov-written",
        "type": "written",
        "domain": "Organic Chemistry",
        "class_level": "11",
        "chapter": "Hydrocarbons",
        "subtopic": "Markovnikov addition",
        "subparts": ["alkene addition", "carbocation stability", "major product"],
        "difficulty": "medium",
        "prompt": "Explain why HBr adds to propene mainly to form 2-bromopropane.",
        "keywords": ["markovnikov", "carbocation", "secondary", "stable", "2-bromopropane", "major"],
        "explanation": "The reaction proceeds through the more stable secondary carbocation, leading to 2-bromopropane as the major product.",
    },
    {
        "id": "org-halo-sn1sn2-mcq",
        "type": "mcq",
        "domain": "Organic Chemistry",
        "class_level": "12",
        "chapter": "Haloalkanes and Haloarenes",
        "subtopic": "SN1 and SN2",
        "subparts": ["substrate effect", "carbocation", "backside attack"],
        "difficulty": "hard",
        "prompt": "Tertiary alkyl halides favor SN1 mainly because they form:",
        "options": [
            {"id": "A", "text": "stable carbocations"},
            {"id": "B", "text": "unstable carbanions"},
            {"id": "C", "text": "stronger C-X bonds"},
            {"id": "D", "text": "planar SN2 transition states"},
        ],
        "answer": "A",
        "explanation": "SN1 proceeds through carbocation formation, and tertiary carbocations are relatively stable.",
    },
    {
        "id": "org-carbonyl-tests-written",
        "type": "written",
        "domain": "Organic Chemistry",
        "class_level": "12",
        "chapter": "Aldehydes, Ketones and Carboxylic Acids",
        "subtopic": "Aldehyde tests",
        "subparts": ["Tollens test", "Fehling test", "oxidation"],
        "difficulty": "medium",
        "prompt": "How can Tollens' reagent distinguish an aldehyde from most ketones?",
        "keywords": ["tollens", "silver mirror", "aldehyde", "oxidized", "ketone", "no reaction"],
        "explanation": "Aldehydes reduce Tollens' reagent to metallic silver and are oxidized; most ketones do not.",
    },
    {
        "id": "org-amines-basicity-written",
        "type": "written",
        "domain": "Organic Chemistry",
        "class_level": "12",
        "chapter": "Amines",
        "subtopic": "Basicity",
        "subparts": ["lone pair availability", "resonance", "alkyl effect"],
        "difficulty": "hard",
        "prompt": "Why is aniline less basic than ethylamine?",
        "keywords": ["lone pair", "resonance", "benzene", "less available", "ethylamine", "alkyl"],
        "explanation": "In aniline, the nitrogen lone pair is delocalized into the benzene ring, so it is less available for protonation than in ethylamine.",
    },
    {
        "id": "ino-periodic-ionization-mcq",
        "type": "mcq",
        "domain": "Inorganic Chemistry",
        "class_level": "11",
        "chapter": "Classification of Elements and Periodicity",
        "subtopic": "Ionization enthalpy trend",
        "subparts": ["effective nuclear charge", "atomic size", "periodic trend"],
        "difficulty": "medium",
        "prompt": "Across a period from left to right, ionization enthalpy generally:",
        "options": [
            {"id": "A", "text": "decreases due to larger size"},
            {"id": "B", "text": "increases due to higher effective nuclear charge"},
            {"id": "C", "text": "stays constant"},
            {"id": "D", "text": "becomes zero"},
        ],
        "answer": "B",
        "explanation": "Effective nuclear charge generally increases across a period, so ionization enthalpy tends to increase.",
    },
    {
        "id": "ino-bonding-vsepr-written",
        "type": "written",
        "domain": "Inorganic Chemistry",
        "class_level": "11",
        "chapter": "Chemical Bonding and Molecular Structure",
        "subtopic": "VSEPR theory",
        "subparts": ["lone pair repulsion", "shape", "bond angle"],
        "difficulty": "medium",
        "prompt": "Why is the bond angle in NH3 smaller than the tetrahedral angle?",
        "keywords": ["lone pair", "repulsion", "bond pair", "107", "tetrahedral", "pyramidal"],
        "explanation": "The lone pair on nitrogen repels bonding pairs more strongly, compressing the H-N-H angle to about 107 degrees.",
    },
    {
        "id": "ino-sblock-flame-mcq",
        "type": "mcq",
        "domain": "Inorganic Chemistry",
        "class_level": "11",
        "chapter": "The s-Block Elements",
        "subtopic": "Flame test",
        "subparts": ["excitation", "emission", "alkali metals"],
        "difficulty": "easy",
        "prompt": "The characteristic flame colours of alkali metals arise due to:",
        "options": [
            {"id": "A", "text": "neutron emission"},
            {"id": "B", "text": "electronic excitation and emission"},
            {"id": "C", "text": "nuclear fission"},
            {"id": "D", "text": "loss of protons"},
        ],
        "answer": "B",
        "explanation": "Heat excites valence electrons; emitted light on return gives characteristic flame colours.",
    },
    {
        "id": "ino-pblock-inertpair-mcq",
        "type": "mcq",
        "domain": "Inorganic Chemistry",
        "class_level": "12",
        "chapter": "The p-Block Elements",
        "subtopic": "Inert pair effect",
        "subparts": ["lower oxidation state", "heavier p-block elements", "ns2 pair"],
        "difficulty": "medium",
        "prompt": "Inert pair effect explains the increasing stability of:",
        "options": [
            {"id": "A", "text": "higher oxidation states down a group"},
            {"id": "B", "text": "lower oxidation states down a group"},
            {"id": "C", "text": "zero oxidation state only"},
            {"id": "D", "text": "only noble gas compounds"},
        ],
        "answer": "B",
        "explanation": "The ns2 pair becomes less available for bonding in heavier p-block elements, stabilizing lower oxidation states.",
    },
    {
        "id": "ino-coordination-oxidation-mcq",
        "type": "mcq",
        "domain": "Inorganic Chemistry",
        "class_level": "12",
        "chapter": "Coordination Compounds",
        "subtopic": "Oxidation number",
        "subparts": ["ligand charge", "complex charge", "metal oxidation state"],
        "difficulty": "medium",
        "prompt": "What is the oxidation state of Co in [Co(NH3)5Cl]Cl2?",
        "options": [
            {"id": "A", "text": "+1"},
            {"id": "B", "text": "+2"},
            {"id": "C", "text": "+3"},
            {"id": "D", "text": "+5"},
        ],
        "answer": "C",
        "explanation": "The complex cation has +2 charge; NH3 is neutral and coordinated Cl is -1, so Co is +3.",
    },
    {
        "id": "ino-dblock-colour-written",
        "type": "written",
        "domain": "Inorganic Chemistry",
        "class_level": "12",
        "chapter": "The d- and f-Block Elements",
        "subtopic": "Colour of transition metal ions",
        "subparts": ["partly filled d orbitals", "d-d transition", "ligand field"],
        "difficulty": "medium",
        "prompt": "Why are many transition metal ions coloured?",
        "keywords": ["partly filled", "d orbital", "d-d transition", "ligand field", "absorbs", "visible"],
        "explanation": "Partly filled d orbitals split in a ligand field; d-d transitions absorb visible light and produce colour.",
    },
    {
        "id": "ino-metallurgy-ellingham-written",
        "type": "written",
        "domain": "Inorganic Chemistry",
        "class_level": "12",
        "chapter": "General Principles and Processes of Isolation of Elements",
        "subtopic": "Ellingham diagram",
        "subparts": ["oxide stability", "temperature", "reducing agent"],
        "difficulty": "hard",
        "prompt": "What does an Ellingham diagram help decide in metallurgy?",
        "keywords": ["oxide", "stability", "reducing agent", "temperature", "delta g", "extraction"],
        "explanation": "Ellingham diagrams compare oxide stability and help choose suitable reducing agents and temperatures.",
    },
]


QUESTION_BANK.extend(
    [
        {
            "id": "chem-stoich-yield-written",
            "type": "written",
            "subject": "Chemistry",
            "domain": "Physical Chemistry",
            "class_level": "11",
            "chapter": "Some Basic Concepts of Chemistry",
            "subtopic": "Percentage yield",
            "subparts": ["theoretical yield", "actual yield", "percentage yield"],
            "difficulty": "medium",
            "prompt": "A reaction has theoretical yield 10 g and actual yield 8 g. Explain how to calculate percentage yield.",
            "keywords": ["actual yield", "theoretical yield", "8", "10", "80", "percentage"],
            "explanation": "Percentage yield is actual yield divided by theoretical yield multiplied by 100, so 8/10 x 100 = 80%.",
        },
        {
            "id": "chem-equilibrium-kc-mcq",
            "type": "mcq",
            "subject": "Chemistry",
            "domain": "Physical Chemistry",
            "class_level": "11",
            "chapter": "Equilibrium",
            "subtopic": "Equilibrium constant",
            "subparts": ["products over reactants", "stoichiometric powers", "constant temperature"],
            "difficulty": "medium",
            "prompt": "For aA + bB <=> cC + dD, the expression for Kc is:",
            "options": [
                {"id": "A", "text": "[A]^a[B]^b/[C]^c[D]^d"},
                {"id": "B", "text": "[C]^c[D]^d/[A]^a[B]^b"},
                {"id": "C", "text": "[C][D]/[A][B] without powers"},
                {"id": "D", "text": "Sum of product concentrations"},
            ],
            "answer": "B",
            "explanation": "Kc equals product concentrations over reactant concentrations, each raised to the balanced stoichiometric coefficient.",
        },
        {
            "id": "org-goc-resonance-written",
            "type": "written",
            "subject": "Chemistry",
            "domain": "Organic Chemistry",
            "class_level": "11",
            "chapter": "Organic Chemistry: Basic Principles",
            "subtopic": "Resonance and acidity",
            "subparts": ["resonance", "conjugate base", "delocalization"],
            "difficulty": "medium",
            "prompt": "Why is phenol more acidic than ethanol?",
            "keywords": ["phenoxide", "resonance", "delocalized", "conjugate base", "ethoxide", "stabilized"],
            "explanation": "Phenoxide ion is stabilized by resonance, while ethoxide has no comparable delocalization.",
        },
        {
            "id": "org-hydrocarbon-anti-mark-mcq",
            "type": "mcq",
            "subject": "Chemistry",
            "domain": "Organic Chemistry",
            "class_level": "11",
            "chapter": "Hydrocarbons",
            "subtopic": "Peroxide effect",
            "subparts": ["anti-Markovnikov", "free radical", "HBr"],
            "difficulty": "medium",
            "prompt": "Anti-Markovnikov addition in the presence of peroxide is most characteristic for:",
            "options": [
                {"id": "A", "text": "HCl addition to alkene"},
                {"id": "B", "text": "HBr addition to alkene"},
                {"id": "C", "text": "HI addition to alkene"},
                {"id": "D", "text": "hydration of alkene"},
            ],
            "answer": "B",
            "explanation": "The peroxide effect operates through a radical mechanism and is observed for HBr addition.",
        },
        {
            "id": "ino-bonding-hybridization-mcq",
            "type": "mcq",
            "subject": "Chemistry",
            "domain": "Inorganic Chemistry",
            "class_level": "11",
            "chapter": "Chemical Bonding and Molecular Structure",
            "subtopic": "Hybridization",
            "subparts": ["steric number", "sp3", "tetrahedral geometry"],
            "difficulty": "medium",
            "prompt": "The central carbon in methane is best described as:",
            "options": [
                {"id": "A", "text": "sp hybridized"},
                {"id": "B", "text": "sp2 hybridized"},
                {"id": "C", "text": "sp3 hybridized"},
                {"id": "D", "text": "unhybridized p"},
            ],
            "answer": "C",
            "explanation": "Methane has four sigma bonds around carbon, giving sp3 hybridization and tetrahedral geometry.",
        },
        {
            "id": "ino-coordination-isomerism-written",
            "type": "written",
            "subject": "Chemistry",
            "domain": "Inorganic Chemistry",
            "class_level": "12",
            "chapter": "Coordination Compounds",
            "subtopic": "Coordination isomerism",
            "subparts": ["ligand exchange", "complex cation", "complex anion"],
            "difficulty": "hard",
            "prompt": "What is coordination isomerism in complexes containing both complex cation and complex anion?",
            "keywords": ["coordination", "isomerism", "ligand", "exchange", "cation", "anion"],
            "explanation": "Coordination isomerism arises when ligands interchange between complex cationic and anionic parts.",
        },
        {
            "id": "chem-solid-defect-mcq",
            "type": "mcq",
            "subject": "Chemistry",
            "domain": "Physical Chemistry",
            "class_level": "12",
            "chapter": "Solid State",
            "subtopic": "Schottky defect",
            "subparts": ["vacancy", "density decreases", "ionic solids"],
            "difficulty": "medium",
            "prompt": "A Schottky defect in an ionic solid mainly involves:",
            "options": [
                {"id": "A", "text": "equal number of cation and anion vacancies"},
                {"id": "B", "text": "an extra ion in an interstitial site only"},
                {"id": "C", "text": "replacement by impurity atom only"},
                {"id": "D", "text": "free electrons in conduction band"},
            ],
            "answer": "A",
            "explanation": "Schottky defects are paired vacancies that preserve electrical neutrality and lower density.",
        },
        {
            "id": "chem-redox-balancing-written",
            "type": "written",
            "subject": "Chemistry",
            "domain": "Physical Chemistry",
            "class_level": "11",
            "chapter": "Redox Reactions",
            "subtopic": "Oxidation number method",
            "subparts": ["oxidation number", "electron change", "charge balance"],
            "difficulty": "medium",
            "prompt": "Explain the main steps of balancing a redox reaction by oxidation number method.",
            "keywords": ["oxidation number", "increase", "decrease", "electron", "balance", "charge"],
            "explanation": "Track oxidation number changes, equalize electron loss and gain, then balance atoms and charge.",
        },
        {
            "id": "chem-atomic-bohr-mcq",
            "type": "mcq",
            "subject": "Chemistry",
            "domain": "Physical Chemistry",
            "class_level": "11",
            "chapter": "Structure of Atom",
            "subtopic": "Bohr model",
            "subparts": ["stationary orbits", "quantized energy", "emission spectrum"],
            "difficulty": "medium",
            "prompt": "In Bohr's model, emission of radiation occurs when an electron:",
            "options": [
                {"id": "A", "text": "moves in the same stationary orbit"},
                {"id": "B", "text": "jumps from higher to lower energy level"},
                {"id": "C", "text": "is at rest in the nucleus"},
                {"id": "D", "text": "has zero angular momentum"},
            ],
            "answer": "B",
            "explanation": "Radiation is emitted when an electron drops from a higher to a lower quantized energy level.",
        },
        {
            "id": "chem-thermo-enthalpy-written",
            "type": "written",
            "subject": "Chemistry",
            "domain": "Physical Chemistry",
            "class_level": "11",
            "chapter": "Thermodynamics",
            "subtopic": "Enthalpy change",
            "subparts": ["heat at constant pressure", "state function", "exo/endothermic"],
            "difficulty": "medium",
            "prompt": "What does enthalpy change tell us for a reaction at constant pressure?",
            "keywords": ["enthalpy", "constant pressure", "heat", "state function", "exothermic", "endothermic"],
            "explanation": "At constant pressure, enthalpy change equals heat exchanged and indicates exothermic or endothermic behavior.",
        },
        {
            "id": "phys-units-dimension-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Mechanics",
            "class_level": "11",
            "chapter": "Units and Measurements",
            "subtopic": "Dimensional analysis",
            "subparts": ["base dimensions", "checking formula", "homogeneity"],
            "difficulty": "easy",
            "prompt": "Dimensional analysis can be used to check:",
            "options": [
                {"id": "A", "text": "numerical value of every constant"},
                {"id": "B", "text": "dimensional consistency of an equation"},
                {"id": "C", "text": "experimental error without data"},
                {"id": "D", "text": "direction of a vector only"},
            ],
            "answer": "B",
            "explanation": "A physically valid equation must be dimensionally homogeneous on both sides.",
        },
        {
            "id": "phys-kinematics-graph-written",
            "type": "written",
            "subject": "Physics",
            "domain": "Mechanics",
            "class_level": "11",
            "chapter": "Motion in a Straight Line",
            "subtopic": "Velocity-time graph",
            "subparts": ["slope", "acceleration", "area", "displacement"],
            "difficulty": "medium",
            "prompt": "In a velocity-time graph, what do slope and area under the graph represent?",
            "keywords": ["slope", "acceleration", "area", "displacement", "velocity-time", "graph"],
            "explanation": "Slope gives acceleration, while area under a velocity-time graph gives displacement.",
        },
        {
            "id": "phys-newton-friction-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Mechanics",
            "class_level": "11",
            "chapter": "Laws of Motion",
            "subtopic": "Limiting friction",
            "subparts": ["normal reaction", "coefficient of friction", "maximum static friction"],
            "difficulty": "medium",
            "prompt": "Maximum static friction is equal to:",
            "options": [
                {"id": "A", "text": "mu_s N"},
                {"id": "B", "text": "N/mu_s"},
                {"id": "C", "text": "mg/mu_s"},
                {"id": "D", "text": "zero for all rough surfaces"},
            ],
            "answer": "A",
            "explanation": "The limiting value of static friction is f_max = mu_s N.",
        },
        {
            "id": "phys-work-energy-written",
            "type": "written",
            "subject": "Physics",
            "domain": "Mechanics",
            "class_level": "11",
            "chapter": "Work, Energy and Power",
            "subtopic": "Work-energy theorem",
            "subparts": ["net work", "change in kinetic energy", "force displacement"],
            "difficulty": "medium",
            "prompt": "State the work-energy theorem and explain what net work changes.",
            "keywords": ["net work", "change", "kinetic energy", "work-energy", "force", "displacement"],
            "explanation": "The theorem states that net work done on a body equals the change in its kinetic energy.",
        },
        {
            "id": "phys-work-energy-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Mechanics",
            "class_level": "11",
            "chapter": "Work, Energy and Power",
            "subtopic": "Conservative force",
            "subparts": ["path independent", "potential energy", "closed loop work"],
            "difficulty": "medium",
            "prompt": "For a conservative force, work done between two points is:",
            "options": [
                {"id": "A", "text": "path independent"},
                {"id": "B", "text": "always positive"},
                {"id": "C", "text": "always zero for any path"},
                {"id": "D", "text": "dependent only on speed"},
            ],
            "answer": "A",
            "explanation": "Work by a conservative force depends only on initial and final positions.",
        },
        {
            "id": "phys-rotation-inertia-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Mechanics",
            "class_level": "11",
            "chapter": "System of Particles and Rotational Motion",
            "subtopic": "Moment of inertia",
            "subparts": ["mass distribution", "axis of rotation", "rotational inertia"],
            "difficulty": "medium",
            "prompt": "Moment of inertia depends on mass and:",
            "options": [
                {"id": "A", "text": "distribution of mass about the axis"},
                {"id": "B", "text": "colour of the body"},
                {"id": "C", "text": "temperature only"},
                {"id": "D", "text": "linear speed only"},
            ],
            "answer": "A",
            "explanation": "Moment of inertia depends on how mass is distributed relative to the chosen axis.",
        },
        {
            "id": "phys-gravitation-orbit-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Mechanics",
            "class_level": "11",
            "chapter": "Gravitation",
            "subtopic": "Orbital speed",
            "subparts": ["centripetal force", "gravity", "sqrt(GM/r)"],
            "difficulty": "medium",
            "prompt": "For a circular orbit around Earth, orbital speed varies with radius r as:",
            "options": [
                {"id": "A", "text": "proportional to r"},
                {"id": "B", "text": "proportional to sqrt(r)"},
                {"id": "C", "text": "proportional to 1/sqrt(r)"},
                {"id": "D", "text": "independent of r"},
            ],
            "answer": "C",
            "explanation": "For circular orbit v = sqrt(GM/r), so speed decreases as radius increases.",
        },
        {
            "id": "phys-shm-energy-written",
            "type": "written",
            "subject": "Physics",
            "domain": "Oscillations and Waves",
            "class_level": "11",
            "chapter": "Oscillations",
            "subtopic": "Energy in SHM",
            "subparts": ["kinetic energy", "potential energy", "total energy constant"],
            "difficulty": "medium",
            "prompt": "How do kinetic and potential energy change during simple harmonic motion?",
            "keywords": ["kinetic", "potential", "total energy", "constant", "mean position", "extreme"],
            "explanation": "In ideal SHM, kinetic and potential energy interchange while total mechanical energy remains constant.",
        },
        {
            "id": "phys-waves-standing-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Oscillations and Waves",
            "class_level": "11",
            "chapter": "Waves",
            "subtopic": "Standing waves",
            "subparts": ["nodes", "antinodes", "superposition"],
            "difficulty": "medium",
            "prompt": "In a standing wave, particles at nodes have:",
            "options": [
                {"id": "A", "text": "maximum displacement"},
                {"id": "B", "text": "zero displacement"},
                {"id": "C", "text": "maximum pressure only"},
                {"id": "D", "text": "random displacement"},
            ],
            "answer": "B",
            "explanation": "Nodes are points of zero displacement in a standing wave.",
        },
        {
            "id": "phys-electrostatics-gauss-written",
            "type": "written",
            "subject": "Physics",
            "domain": "Electrodynamics",
            "class_level": "12",
            "chapter": "Electrostatics",
            "subtopic": "Gauss law",
            "subparts": ["electric flux", "enclosed charge", "symmetry"],
            "difficulty": "medium",
            "prompt": "State Gauss law and explain why symmetry matters when using it.",
            "keywords": ["electric flux", "enclosed charge", "epsilon", "symmetry", "gaussian surface", "field"],
            "explanation": "Gauss law relates total electric flux through a closed surface to enclosed charge; symmetry makes field evaluation simple.",
        },
        {
            "id": "phys-electrostatics-flux-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Electrodynamics",
            "class_level": "12",
            "chapter": "Electrostatics",
            "subtopic": "Electric flux",
            "subparts": ["area vector", "field component", "cos theta"],
            "difficulty": "medium",
            "prompt": "Electric flux through a flat area A in uniform field E is maximum when:",
            "options": [
                {"id": "A", "text": "area vector is parallel to E"},
                {"id": "B", "text": "area vector is perpendicular to E"},
                {"id": "C", "text": "area is zero"},
                {"id": "D", "text": "field is zero"},
            ],
            "answer": "A",
            "explanation": "Flux is EA cos theta, maximum when the area vector is parallel to the electric field.",
        },
        {
            "id": "phys-current-wheatstone-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Electrodynamics",
            "class_level": "12",
            "chapter": "Current Electricity",
            "subtopic": "Wheatstone bridge",
            "subparts": ["balanced bridge", "no galvanometer current", "resistance ratio"],
            "difficulty": "medium",
            "prompt": "In a balanced Wheatstone bridge, current through the galvanometer is:",
            "options": [
                {"id": "A", "text": "maximum"},
                {"id": "B", "text": "zero"},
                {"id": "C", "text": "equal to battery current"},
                {"id": "D", "text": "independent of resistance ratio"},
            ],
            "answer": "B",
            "explanation": "At balance, the two junctions connected by the galvanometer are at the same potential.",
        },
        {
            "id": "phys-current-series-written",
            "type": "written",
            "subject": "Physics",
            "domain": "Electrodynamics",
            "class_level": "12",
            "chapter": "Current Electricity",
            "subtopic": "Series and parallel resistance",
            "subparts": ["series current", "parallel voltage", "equivalent resistance"],
            "difficulty": "medium",
            "prompt": "Contrast current and voltage behavior in series and parallel resistor combinations.",
            "keywords": ["series", "same current", "parallel", "same voltage", "equivalent resistance", "resistor"],
            "explanation": "Series resistors carry same current; parallel branches share same voltage.",
        },
        {
            "id": "phys-magnetism-lorentz-written",
            "type": "written",
            "subject": "Physics",
            "domain": "Electrodynamics",
            "class_level": "12",
            "chapter": "Moving Charges and Magnetism",
            "subtopic": "Lorentz force",
            "subparts": ["qvB", "right hand rule", "perpendicular force"],
            "difficulty": "medium",
            "prompt": "Explain the direction of magnetic force on a moving positive charge in a magnetic field.",
            "keywords": ["qvb", "right hand", "perpendicular", "velocity", "magnetic field", "positive charge"],
            "explanation": "For a positive charge, magnetic force direction follows v x B and is perpendicular to both velocity and field.",
        },
        {
            "id": "phys-emi-lenz-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Electrodynamics",
            "class_level": "12",
            "chapter": "Electromagnetic Induction",
            "subtopic": "Lenz law",
            "subparts": ["opposes change", "induced emf", "energy conservation"],
            "difficulty": "medium",
            "prompt": "Lenz law states that induced current flows in a direction that:",
            "options": [
                {"id": "A", "text": "aids the change in magnetic flux"},
                {"id": "B", "text": "opposes the change in magnetic flux"},
                {"id": "C", "text": "is always clockwise"},
                {"id": "D", "text": "does not depend on flux"},
            ],
            "answer": "B",
            "explanation": "The induced current opposes the change in magnetic flux that produces it.",
        },
        {
            "id": "phys-optics-lens-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Optics",
            "class_level": "12",
            "chapter": "Ray Optics and Optical Instruments",
            "subtopic": "Lens formula",
            "subparts": ["1/v - 1/u", "focal length", "sign convention"],
            "difficulty": "medium",
            "prompt": "The thin lens formula using Cartesian sign convention is:",
            "options": [
                {"id": "A", "text": "1/f = 1/v - 1/u"},
                {"id": "B", "text": "1/f = 1/u - 1/v"},
                {"id": "C", "text": "f = u + v"},
                {"id": "D", "text": "f = uv"},
            ],
            "answer": "A",
            "explanation": "The standard thin lens relation is 1/f = 1/v - 1/u with sign convention.",
        },
        {
            "id": "phys-optics-power-written",
            "type": "written",
            "subject": "Physics",
            "domain": "Optics",
            "class_level": "12",
            "chapter": "Ray Optics and Optical Instruments",
            "subtopic": "Power of lens",
            "subparts": ["dioptre", "inverse focal length", "converging/diverging"],
            "difficulty": "medium",
            "prompt": "What is power of a lens and how is it related to focal length?",
            "keywords": ["power", "dioptre", "inverse", "focal length", "metre", "converging"],
            "explanation": "Lens power P = 1/f when f is in metres; its unit is dioptre.",
        },
        {
            "id": "phys-modern-photoelectric-written",
            "type": "written",
            "subject": "Physics",
            "domain": "Modern Physics",
            "class_level": "12",
            "chapter": "Dual Nature of Radiation and Matter",
            "subtopic": "Photoelectric effect",
            "subparts": ["threshold frequency", "work function", "kinetic energy"],
            "difficulty": "medium",
            "prompt": "Explain threshold frequency in the photoelectric effect.",
            "keywords": ["threshold frequency", "minimum", "work function", "photoelectron", "kinetic energy", "emission"],
            "explanation": "Threshold frequency is the minimum frequency needed for photon energy to overcome the work function and emit electrons.",
        },
        {
            "id": "phys-modern-threshold-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Modern Physics",
            "class_level": "12",
            "chapter": "Dual Nature of Radiation and Matter",
            "subtopic": "Photoelectric effect",
            "subparts": ["frequency", "intensity", "stopping potential"],
            "difficulty": "medium",
            "prompt": "Increasing light intensity above threshold frequency mainly increases:",
            "options": [
                {"id": "A", "text": "maximum kinetic energy only"},
                {"id": "B", "text": "number of emitted photoelectrons"},
                {"id": "C", "text": "threshold frequency"},
                {"id": "D", "text": "work function"},
            ],
            "answer": "B",
            "explanation": "Intensity affects the number of photons, hence photoelectric current, not the maximum kinetic energy.",
        },
        {
            "id": "phys-semiconductor-diode-mcq",
            "type": "mcq",
            "subject": "Physics",
            "domain": "Modern Physics",
            "class_level": "12",
            "chapter": "Semiconductor Electronics",
            "subtopic": "p-n junction diode",
            "subparts": ["forward bias", "depletion region", "current"],
            "difficulty": "medium",
            "prompt": "In forward bias of a p-n junction diode, the depletion width generally:",
            "options": [
                {"id": "A", "text": "decreases"},
                {"id": "B", "text": "increases without limit"},
                {"id": "C", "text": "becomes independent of voltage"},
                {"id": "D", "text": "turns metallic"},
            ],
            "answer": "A",
            "explanation": "Forward bias lowers the barrier potential and narrows the depletion region.",
        },
        {
            "id": "math-quadratic-discriminant-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Algebra",
            "class_level": "11",
            "chapter": "Complex Numbers and Quadratic Equations",
            "subtopic": "Discriminant",
            "subparts": ["b^2-4ac", "real roots", "nature of roots"],
            "difficulty": "easy",
            "prompt": "A quadratic equation ax^2 + bx + c = 0 has two distinct real roots when:",
            "options": [
                {"id": "A", "text": "b^2 - 4ac > 0"},
                {"id": "B", "text": "b^2 - 4ac = 0"},
                {"id": "C", "text": "b^2 - 4ac < 0"},
                {"id": "D", "text": "a = 0"},
            ],
            "answer": "A",
            "explanation": "The discriminant is positive for two distinct real roots.",
        },
        {
            "id": "math-quadratic-roots-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Algebra",
            "class_level": "11",
            "chapter": "Complex Numbers and Quadratic Equations",
            "subtopic": "Sum and product of roots",
            "subparts": ["sum alpha+beta", "product alphabeta", "coefficient relation"],
            "difficulty": "medium",
            "prompt": "For ax^2 + bx + c = 0, state the sum and product of roots.",
            "keywords": ["sum", "-b/a", "product", "c/a", "roots", "coefficient"],
            "explanation": "For roots alpha and beta, alpha + beta = -b/a and alpha beta = c/a.",
        },
        {
            "id": "math-sequence-gp-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Algebra",
            "class_level": "11",
            "chapter": "Sequences and Series",
            "subtopic": "Geometric progression",
            "subparts": ["common ratio", "nth term", "sum formula"],
            "difficulty": "medium",
            "prompt": "Explain how the nth term of a geometric progression is built from first term and common ratio.",
            "keywords": ["geometric progression", "first term", "common ratio", "nth term", "a r", "n-1"],
            "explanation": "The nth term of a GP is a r^(n-1), where a is first term and r is common ratio.",
        },
        {
            "id": "math-sequence-ap-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Algebra",
            "class_level": "11",
            "chapter": "Sequences and Series",
            "subtopic": "Arithmetic progression",
            "subparts": ["common difference", "nth term", "linear pattern"],
            "difficulty": "easy",
            "prompt": "The nth term of an AP with first term a and common difference d is:",
            "options": [
                {"id": "A", "text": "a + (n - 1)d"},
                {"id": "B", "text": "ar^(n - 1)"},
                {"id": "C", "text": "a/(n - 1)d"},
                {"id": "D", "text": "nd/a"},
            ],
            "answer": "A",
            "explanation": "An AP increases by a constant difference, so nth term is a + (n - 1)d.",
        },
        {
            "id": "math-binomial-term-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Algebra",
            "class_level": "11",
            "chapter": "Binomial Theorem",
            "subtopic": "General term",
            "subparts": ["nCr", "powers", "term index"],
            "difficulty": "medium",
            "prompt": "The general term in the expansion of (a + b)^n is:",
            "options": [
                {"id": "A", "text": "nCr a^(n-r) b^r"},
                {"id": "B", "text": "nPr a^r b^r"},
                {"id": "C", "text": "a^n + b^n only"},
                {"id": "D", "text": "r! a b"},
            ],
            "answer": "A",
            "explanation": "The binomial expansion has terms C(n, r) a^(n-r) b^r.",
        },
        {
            "id": "math-trig-equation-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Trigonometry",
            "class_level": "11",
            "chapter": "Trigonometric Functions",
            "subtopic": "Principal solutions",
            "subparts": ["periodicity", "general solution", "quadrant"],
            "difficulty": "medium",
            "prompt": "When solving sin x = 1/2, why must the general solution include periodicity?",
            "keywords": ["sin", "1/2", "periodicity", "general solution", "pi", "quadrant"],
            "explanation": "Trigonometric equations repeat periodically, so all valid angles must be represented, not just one principal value.",
        },
        {
            "id": "math-straight-line-slope-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Coordinate Geometry",
            "class_level": "11",
            "chapter": "Straight Lines",
            "subtopic": "Slope",
            "subparts": ["rise over run", "tan theta", "line inclination"],
            "difficulty": "easy",
            "prompt": "The slope of a line making angle theta with the positive x-axis is:",
            "options": [
                {"id": "A", "text": "sin theta"},
                {"id": "B", "text": "cos theta"},
                {"id": "C", "text": "tan theta"},
                {"id": "D", "text": "cot theta"},
            ],
            "answer": "C",
            "explanation": "Slope m equals tan theta, where theta is the angle of inclination.",
        },
        {
            "id": "math-circle-tangent-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Coordinate Geometry",
            "class_level": "11",
            "chapter": "Conic Sections",
            "subtopic": "Circle tangent",
            "subparts": ["radius perpendicular", "point of contact", "tangent line"],
            "difficulty": "medium",
            "prompt": "State the geometric relationship between a circle's radius and tangent at the point of contact.",
            "keywords": ["radius", "perpendicular", "tangent", "point of contact", "circle", "90"],
            "explanation": "The radius to the point of contact is perpendicular to the tangent.",
        },
        {
            "id": "math-limit-derivative-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Calculus",
            "class_level": "11",
            "chapter": "Limits and Derivatives",
            "subtopic": "Derivative as rate of change",
            "subparts": ["limit", "instantaneous rate", "slope of tangent"],
            "difficulty": "medium",
            "prompt": "The derivative of a function at a point represents:",
            "options": [
                {"id": "A", "text": "area under the curve only"},
                {"id": "B", "text": "instantaneous rate of change"},
                {"id": "C", "text": "average of all function values"},
                {"id": "D", "text": "domain of the function"},
            ],
            "answer": "B",
            "explanation": "Derivative at a point is the instantaneous rate of change or slope of the tangent.",
        },
        {
            "id": "math-limit-continuity-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Calculus",
            "class_level": "11",
            "chapter": "Limits and Derivatives",
            "subtopic": "Continuity",
            "subparts": ["left limit", "right limit", "function value"],
            "difficulty": "medium",
            "prompt": "What must be true for a function to be continuous at x = a?",
            "keywords": ["left limit", "right limit", "function value", "equal", "continuous", "a"],
            "explanation": "Continuity at a requires left limit, right limit, and f(a) to exist and be equal.",
        },
        {
            "id": "math-aod-monotonic-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Calculus",
            "class_level": "12",
            "chapter": "Applications of Derivatives",
            "subtopic": "Increasing and decreasing functions",
            "subparts": ["first derivative", "positive derivative", "negative derivative"],
            "difficulty": "medium",
            "prompt": "How does the sign of first derivative help decide whether a function is increasing or decreasing?",
            "keywords": ["first derivative", "positive", "increasing", "negative", "decreasing", "interval"],
            "explanation": "A positive derivative on an interval indicates increasing behavior; a negative derivative indicates decreasing behavior.",
        },
        {
            "id": "math-aod-tangent-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Calculus",
            "class_level": "12",
            "chapter": "Applications of Derivatives",
            "subtopic": "Tangent slope",
            "subparts": ["derivative", "slope", "point"],
            "difficulty": "medium",
            "prompt": "The slope of the tangent to y = f(x) at x = a is:",
            "options": [
                {"id": "A", "text": "f(a)"},
                {"id": "B", "text": "f'(a)"},
                {"id": "C", "text": "a/f(a)"},
                {"id": "D", "text": "integral of f from 0 to a"},
            ],
            "answer": "B",
            "explanation": "The derivative at the point gives the slope of the tangent.",
        },
        {
            "id": "math-integration-substitution-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Calculus",
            "class_level": "12",
            "chapter": "Integrals",
            "subtopic": "Substitution method",
            "subparts": ["change of variable", "differential", "simplification"],
            "difficulty": "medium",
            "prompt": "The substitution method in integration is most useful when:",
            "options": [
                {"id": "A", "text": "a part of the integrand and its derivative appear"},
                {"id": "B", "text": "the integrand is always constant"},
                {"id": "C", "text": "limits are absent only"},
                {"id": "D", "text": "the variable cannot be changed"},
            ],
            "answer": "A",
            "explanation": "Substitution simplifies an integral when a function and its derivative-like factor appear together.",
        },
        {
            "id": "math-differential-equation-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Calculus",
            "class_level": "12",
            "chapter": "Differential Equations",
            "subtopic": "Order and degree",
            "subparts": ["highest derivative", "polynomial in derivatives", "degree"],
            "difficulty": "medium",
            "prompt": "Define order and degree of a differential equation.",
            "keywords": ["order", "highest derivative", "degree", "power", "polynomial", "derivatives"],
            "explanation": "Order is the highest derivative present; degree is the power of the highest derivative when the equation is polynomial in derivatives.",
        },
        {
            "id": "math-matrices-determinant-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Algebra",
            "class_level": "12",
            "chapter": "Matrices",
            "subtopic": "Invertibility",
            "subparts": ["determinant", "non-zero", "inverse matrix"],
            "difficulty": "medium",
            "prompt": "A square matrix is invertible if its determinant is:",
            "options": [
                {"id": "A", "text": "zero"},
                {"id": "B", "text": "non-zero"},
                {"id": "C", "text": "negative only"},
                {"id": "D", "text": "equal to its trace"},
            ],
            "answer": "B",
            "explanation": "A square matrix has an inverse exactly when its determinant is non-zero.",
        },
        {
            "id": "math-matrices-invertible-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Algebra",
            "class_level": "12",
            "chapter": "Matrices",
            "subtopic": "Inverse matrix",
            "subparts": ["adjoint", "determinant", "non-zero determinant"],
            "difficulty": "medium",
            "prompt": "Why does a matrix with zero determinant not have an inverse?",
            "keywords": ["zero determinant", "inverse", "singular", "adjoint", "non-zero", "matrix"],
            "explanation": "The inverse formula divides by determinant; when determinant is zero, the matrix is singular and not invertible.",
        },
        {
            "id": "math-vector-dot-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Vectors and 3D",
            "class_level": "12",
            "chapter": "Vector Algebra",
            "subtopic": "Dot product",
            "subparts": ["magnitude", "cos theta", "projection"],
            "difficulty": "medium",
            "prompt": "The dot product of two perpendicular non-zero vectors is:",
            "options": [
                {"id": "A", "text": "zero"},
                {"id": "B", "text": "one"},
                {"id": "C", "text": "their magnitude product"},
                {"id": "D", "text": "undefined"},
            ],
            "answer": "A",
            "explanation": "Dot product is |a||b|cos theta; for 90 degrees, cos theta is zero.",
        },
        {
            "id": "math-3d-plane-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Vectors and 3D",
            "class_level": "12",
            "chapter": "Three Dimensional Geometry",
            "subtopic": "Plane normal",
            "subparts": ["normal vector", "plane equation", "direction ratios"],
            "difficulty": "medium",
            "prompt": "What role does the normal vector play in the equation of a plane?",
            "keywords": ["normal vector", "perpendicular", "plane", "equation", "direction ratios", "dot product"],
            "explanation": "A plane equation uses a normal vector perpendicular to every direction lying in the plane.",
        },
        {
            "id": "math-probability-conditional-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Probability and Statistics",
            "class_level": "12",
            "chapter": "Probability",
            "subtopic": "Conditional probability",
            "subparts": ["given event", "intersection", "reduced sample space"],
            "difficulty": "medium",
            "prompt": "Explain the meaning of P(A|B) in conditional probability.",
            "keywords": ["conditional probability", "given", "B occurred", "intersection", "reduced sample space", "P(A|B)"],
            "explanation": "P(A|B) is the probability of A when B is known to have occurred, using B as the sample space.",
        },
        {
            "id": "math-probability-bayes-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Probability and Statistics",
            "class_level": "12",
            "chapter": "Probability",
            "subtopic": "Bayes theorem",
            "subparts": ["prior", "likelihood", "posterior"],
            "difficulty": "hard",
            "prompt": "Bayes theorem is used to find:",
            "options": [
                {"id": "A", "text": "posterior probability from prior and likelihood"},
                {"id": "B", "text": "derivative of probability"},
                {"id": "C", "text": "area of a triangle"},
                {"id": "D", "text": "matrix inverse only"},
            ],
            "answer": "A",
            "explanation": "Bayes theorem updates probability of a cause or hypothesis after observing evidence.",
        },
        {
            "id": "math-complex-argand-mcq",
            "type": "mcq",
            "subject": "Mathematics",
            "domain": "Algebra",
            "class_level": "11",
            "chapter": "Complex Numbers and Quadratic Equations",
            "subtopic": "Argand plane",
            "subparts": ["real axis", "imaginary axis", "modulus"],
            "difficulty": "medium",
            "prompt": "In the Argand plane, the point representing z = a + ib has coordinates:",
            "options": [
                {"id": "A", "text": "(a, b)"},
                {"id": "B", "text": "(b, a)"},
                {"id": "C", "text": "(a + b, 0)"},
                {"id": "D", "text": "(0, ab)"},
            ],
            "answer": "A",
            "explanation": "The real part is plotted on x-axis and imaginary part on y-axis.",
        },
        {
            "id": "math-permutation-restriction-written",
            "type": "written",
            "subject": "Mathematics",
            "domain": "Algebra",
            "class_level": "11",
            "chapter": "Permutations and Combinations",
            "subtopic": "Restriction method",
            "subparts": ["cases", "complement", "arrangement"],
            "difficulty": "medium",
            "prompt": "When counting arrangements with restrictions, why is the complement method often useful?",
            "keywords": ["restriction", "complement", "total", "unwanted", "arrangements", "cases"],
            "explanation": "Counting total arrangements and subtracting unwanted cases can be simpler than direct casework.",
        },
    ]
)

for question in QUESTION_BANK:
    question.setdefault("subject", "Chemistry")


INITIAL_TEST_IDS = [
    "phy-stoich-limiting-mcq",
    "phy-equilibrium-lechatelier-written",
    "org-goc-acidity-mcq",
    "org-hydrocarbon-markovnikov-written",
    "ino-bonding-vsepr-written",
    "ino-coordination-oxidation-mcq",
    "phys-units-dimension-mcq",
    "phys-work-energy-written",
    "phys-current-wheatstone-mcq",
    "phys-modern-photoelectric-written",
    "phys-optics-lens-mcq",
    "phys-electrostatics-gauss-written",
    "math-quadratic-discriminant-mcq",
    "math-sequence-gp-written",
    "math-limit-derivative-mcq",
    "math-aod-monotonic-written",
    "math-matrices-determinant-mcq",
    "math-probability-conditional-written",
]


def _question_by_id() -> dict[str, dict[str, Any]]:
    return {question["id"]: question for question in QUESTION_BANK}


def _public_question(question: dict[str, Any], reason: str | None = None) -> dict[str, Any]:
    public = {
        "id": question["id"],
        "type": question["type"],
        "subject": question["subject"],
        "domain": question["domain"],
        "class_level": question["class_level"],
        "chapter": question["chapter"],
        "subtopic": question["subtopic"],
        "subparts": question["subparts"],
        "difficulty": question["difficulty"],
        "prompt": question["prompt"],
    }
    if question["type"] == "mcq":
        public["options"] = question["options"]
    if reason:
        public["selection_reason"] = reason
    return public


def _build_test(
    question_ids: list[str],
    attempt_number: int,
    purpose: str,
    reasons: dict[str, str] | None = None,
    selection_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bank = _question_by_id()
    questions = [
        _public_question(bank[question_id], (reasons or {}).get(question_id))
        for question_id in question_ids
        if question_id in bank
    ]
    test = {
        "test_id": f"cbse-jee-pcm-attempt-{attempt_number}",
        "attempt_number": attempt_number,
        "title": "Evidence Capture: PCM Diagnostic" if attempt_number == 1 else f"Adaptive Revision Test {attempt_number}",
        "purpose": purpose,
        "question_count": len(questions),
        "mix": {
            "mcq": sum(1 for item in questions if item["type"] == "mcq"),
            "written": sum(1 for item in questions if item["type"] == "written"),
        },
        "coverage": sorted({item["subject"] for item in questions}),
        "domain_coverage": sorted({item["domain"] for item in questions}),
        "syllabus_basis": [
            "CBSE Class 11/12 Physics",
            "CBSE Class 11/12 Chemistry",
            "CBSE Class 11/12 Mathematics",
            "JEE Main Paper 1 PCM pattern",
        ],
        "questions": questions,
    }
    if selection_policy:
        test["selection_policy"] = selection_policy
    return test


def initial_chemistry_test() -> dict[str, Any]:
    return _build_test(
        INITIAL_TEST_IDS,
        1,
        "Balanced PCM evidence capture. The answers feed an action router that chooses the next learning mode.",
    )


def initial_pcm_test() -> dict[str, Any]:
    return initial_chemistry_test()


def _normalise_answer(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _score_written(question: dict[str, Any], answer: str) -> tuple[float, list[str], list[str]]:
    text = answer.lower()
    keywords = question.get("keywords", [])
    found = []
    missing = []
    for keyword in keywords:
        if keyword.lower() in text:
            found.append(keyword)
        else:
            missing.append(keyword)

    if not answer:
        return 0.0, found, keywords

    coverage = len(found) / max(len(keywords), 1)
    length_bonus = 0.12 if len(answer.split()) >= 18 else 0.0
    score = min(1.0, coverage + length_bonus)
    return score, found, missing


def _score_question(question: dict[str, Any], raw_answer: Any) -> dict[str, Any]:
    answer = _normalise_answer(raw_answer)
    if question["type"] == "mcq":
        selected = answer.upper()
        correct = selected == question["answer"]
        return {
            "question_id": question["id"],
            "type": question["type"],
            "subject": question["subject"],
            "domain": question["domain"],
            "class_level": question["class_level"],
            "chapter": question["chapter"],
            "subtopic": question["subtopic"],
            "subparts": question["subparts"],
            "difficulty": question["difficulty"],
            "prompt": question["prompt"],
            "answer": selected,
            "correct_answer": question["answer"],
            "score": 1.0 if correct else 0.0,
            "correct": correct,
            "concepts_found": question["subparts"] if correct else [],
            "concepts_missing": [] if correct else question["subparts"],
            "feedback": question["explanation"] if correct else f"Correct answer: {question['answer']}. {question['explanation']}",
        }

    score, found, missing = _score_written(question, answer)
    return {
        "question_id": question["id"],
        "type": question["type"],
        "subject": question["subject"],
        "domain": question["domain"],
        "class_level": question["class_level"],
        "chapter": question["chapter"],
        "subtopic": question["subtopic"],
        "subparts": question["subparts"],
        "difficulty": question["difficulty"],
        "prompt": question["prompt"],
        "answer": answer,
        "score": round(score, 2),
        "correct": score >= 0.72,
        "concepts_found": found,
        "concepts_missing": missing[:5],
        "feedback": question["explanation"] if score >= 0.72 else f"Missing key ideas: {', '.join(missing[:4])}. {question['explanation']}",
    }


def _bucket_stats(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[item[key]].append(item)

    rows = []
    for name, values in grouped.items():
        average = sum(value["score"] for value in values) / len(values)
        missing = []
        for value in values:
            missing.extend(value["concepts_missing"])
        rows.append(
            {
                "name": name,
                "score": round(average * 100),
                "attempted": len(values),
                "secure": sum(1 for value in values if value["correct"]),
                "status": "strong" if average >= 0.78 else "shaky" if average >= 0.48 else "weak",
                "missing_concepts": sorted(set(missing))[:6],
            }
        )
    return sorted(rows, key=lambda row: (row["score"], row["name"]))


def _proof_analysis(scored: list[dict[str, Any]]) -> dict[str, Any]:
    strong = [item for item in scored if item["score"] >= 0.78]
    partial = [item for item in scored if 0.38 <= item["score"] < 0.78]
    weak = [item for item in scored if item["score"] < 0.38]
    missing_subparts = sorted({part for item in weak + partial for part in item["concepts_missing"]})[:8]

    return {
        "proves": [
            f"{item['subject']} / {item['domain']} / {item['chapter']} / {item['subtopic']}"
            for item in strong[:5]
        ],
        "partially_proves": [
            f"{item['subject']} / {item['domain']} / {item['chapter']} / {item['subtopic']}"
            for item in partial[:5]
        ],
        "does_not_yet_prove": [
            f"{item['subject']} / {item['domain']} / {item['chapter']} / {item['subtopic']}"
            for item in weak[:5]
        ],
        "missing_subparts": missing_subparts,
        "next_best_improvement": (
            f"Repair {weak[0]['subject']} / {weak[0]['chapter']} -> {weak[0]['subtopic']} first."
            if weak
            else "Move to mixed timed revision with written explanations."
        ),
    }


def _jee_readiness(scored: list[dict[str, Any]]) -> dict[str, Any]:
    high_yield = [
        item
        for item in scored
        if item["chapter"] in JEE_HIGH_YIELD.get(item["subject"], set())
    ]
    base = high_yield or scored
    high_yield_score = round(sum(item["score"] for item in base) / len(base) * 100) if base else 0
    priority_gaps = [
        f"{item['subject']} / {item['chapter']} / {item['subtopic']}"
        for item in high_yield
        if item["score"] < 0.72
    ][:6]
    subject_load = defaultdict(int)
    for item in scored:
        subject_load[item["subject"]] += 1

    return {
        "high_yield_score": high_yield_score,
        "priority_gaps": priority_gaps,
        "subject_load": dict(sorted(subject_load.items())),
        "paper_pattern_notes": [
            "JEE Paper 1 preparation must stay balanced across Physics, Chemistry, and Mathematics.",
            "Mathematics is split into algebra, calculus, coordinate geometry, vectors/3D, and probability so the analysis does not hide broad weaknesses.",
            "High-yield remediation is weighted toward modern physics, current electricity, electrostatics, optics, coordination chemistry, equilibrium, calculus, algebra, coordinate geometry, vectors/3D, and probability.",
        ],
    }


def _attempt_delta(history: list[dict[str, Any]], current_score: int) -> dict[str, Any]:
    if not history:
        return {
            "baseline_score": current_score,
            "previous_score": None,
            "delta_from_first": 0,
            "delta_from_previous": 0,
            "trend": "first_attempt",
        }

    first = int(history[0].get("overall_score", current_score))
    previous = int(history[-1].get("overall_score", current_score))
    delta_previous = current_score - previous
    return {
        "baseline_score": first,
        "previous_score": previous,
        "delta_from_first": current_score - first,
        "delta_from_previous": delta_previous,
        "trend": "improved" if delta_previous > 0 else "regressed" if delta_previous < 0 else "flat",
    }


def _schedule(attempt_number: int, score: int, weak_focus: list[str]) -> dict[str, Any]:
    next_index = min(max(attempt_number - 1, 0), len(REVIEW_GAPS) - 1)
    today = date.today()
    stability = max(1.6, 2.0 + score / 18)
    points = [
        {
            "day": day,
            "date": (today + timedelta(days=day)).isoformat(),
            "predicted_retention": round(exp(-day / stability), 2),
        }
        for day in REVIEW_GAPS
    ]
    return {
        "cadence_days": REVIEW_GAPS,
        "next_retake_in_days": REVIEW_GAPS[next_index],
        "next_retake_date": (today + timedelta(days=REVIEW_GAPS[next_index])).isoformat(),
        "focus": weak_focus[:4],
        "mix_rule": "Next test uses about 80% weak or missed concepts and 20% retained concepts; 40-60% of questions repeat earlier work and the rest are fresh variants.",
        "retention_curve": {
            "model": "personalized_half_life_inspired",
            "stability_days": round(stability, 2),
            "points": points,
        },
    }


def _scored_stub(question: dict[str, Any], score: float) -> dict[str, Any]:
    return {
        "question_id": question["id"],
        "subject": question["subject"],
        "domain": question["domain"],
        "chapter": question["chapter"],
        "subtopic": question["subtopic"],
        "score": score,
    }


def _select_revision_questions(scored: list[dict[str, Any]], attempt_number: int, history: list[dict[str, Any]]) -> dict[str, Any]:
    bank = _question_by_id()
    target_count = 12 + (attempt_number % 3)
    repeat_ratio = [0.46, 0.50, 0.58][(attempt_number - 1) % 3]
    repeat_target = round(target_count * repeat_ratio)
    weak_target = round(target_count * 0.80)
    strong_target = target_count - weak_target

    history_wrong_ids: list[str] = []
    history_correct_ids: list[str] = []
    for attempt in history:
        if not isinstance(attempt, dict):
            continue
        history_wrong_ids.extend(str(item) for item in attempt.get("wrong_question_ids", []) if item in bank)
        history_correct_ids.extend(str(item) for item in attempt.get("correct_question_ids", []) if item in bank)

    current_correct_ids = {item["question_id"] for item in scored if item["score"] >= 0.72}
    current_wrong_ids = {item["question_id"] for item in scored if item["score"] < 0.72}
    history_weak_items = [
        _scored_stub(bank[question_id], 0.0)
        for question_id in dict.fromkeys(history_wrong_ids)
        if question_id not in current_correct_ids
    ]
    history_strong_items = [
        _scored_stub(bank[question_id], 1.0)
        for question_id in dict.fromkeys(history_correct_ids)
        if question_id not in current_wrong_ids
    ]

    weak_items = [item for item in scored if item["score"] < 0.72]
    strong_items = [item for item in scored if item["score"] >= 0.72]
    current_ids = {item["question_id"] for item in scored}
    seen_attempt_ids = current_ids | set(history_wrong_ids) | set(history_correct_ids)
    weak_items.extend(item for item in history_weak_items if item["question_id"] not in current_ids)
    strong_items.extend(item for item in history_strong_items if item["question_id"] not in current_ids)

    def balanced_ids(items: list[dict[str, Any]]) -> list[str]:
        buckets: dict[str, list[str]] = defaultdict(list)
        for item in items:
            buckets[item["subject"]].append(item["question_id"])
        ordered = []
        subject_order = ["Physics", "Chemistry", "Mathematics"]
        while any(buckets.values()):
            for subject in subject_order:
                if buckets[subject]:
                    ordered.append(buckets[subject].pop(0))
            for subject in sorted(set(buckets) - set(subject_order)):
                if buckets[subject]:
                    ordered.append(buckets[subject].pop(0))
        return ordered

    weak_ids = balanced_ids(weak_items)
    strong_ids = balanced_ids(strong_items)
    selected: list[dict[str, Any]] = []
    reasons: dict[str, str] = {}

    def add(question: dict[str, Any], reason: str) -> bool:
        if question["id"] in reasons:
            return False
        selected.append(question)
        reasons[question["id"]] = reason
        return True

    def add_from_ids(question_ids: list[str], count: int, reason: str) -> None:
        for question_id in question_ids:
            if len([item for item in selected if item["id"] in seen_attempt_ids]) >= repeat_target:
                break
            if count <= 0:
                break
            question = bank.get(question_id)
            if question and add(question, reason):
                count -= 1

    def related_pool(items: list[dict[str, Any]], exclude_seen: bool) -> list[dict[str, Any]]:
        item_ids = {item["question_id"] for item in items}
        exact = {
            (item["subject"], item["domain"], item["chapter"], item["subtopic"])
            for item in items
        }
        chapters = {(item["subject"], item["chapter"]) for item in items}
        domains = {(item["subject"], item["domain"]) for item in items}
        subjects = {item["subject"] for item in items}
        ordered: list[dict[str, Any]] = []
        for level in ("exact", "chapter", "domain", "subject"):
            for question in QUESTION_BANK:
                if question["id"] in item_ids or question["id"] in reasons:
                    continue
                if exclude_seen and question["id"] in seen_attempt_ids:
                    continue
                if level == "exact" and (question["subject"], question["domain"], question["chapter"], question["subtopic"]) not in exact:
                    continue
                if level == "chapter" and (question["subject"], question["chapter"]) not in chapters:
                    continue
                if level == "domain" and (question["subject"], question["domain"]) not in domains:
                    continue
                if level == "subject" and question["subject"] not in subjects:
                    continue
                ordered.append(question)
        deduped = []
        seen = set()
        for question in ordered:
            if question["id"] not in seen:
                deduped.append(question)
                seen.add(question["id"])
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for question in deduped:
            buckets[question["subject"]].append(question)
        balanced = []
        subject_order = ["Physics", "Chemistry", "Mathematics"]
        while any(buckets.values()):
            for subject in subject_order:
                if buckets[subject]:
                    balanced.append(buckets[subject].pop(0))
            for subject in sorted(set(buckets) - set(subject_order)):
                if buckets[subject]:
                    balanced.append(buckets[subject].pop(0))
        return balanced

    weak_repeat_target = min(len(weak_ids), max(1, repeat_target // 2)) if weak_ids else 0
    strong_repeat_target = repeat_target - weak_repeat_target
    if strong_repeat_target > len(strong_ids):
        weak_repeat_target = min(len(weak_ids), weak_repeat_target + strong_repeat_target - len(strong_ids))
        strong_repeat_target = min(strong_repeat_target, len(strong_ids))

    add_from_ids(weak_ids, weak_repeat_target, "repeat missed question for error audit")
    add_from_ids(strong_ids, strong_repeat_target, "repeat correct question for retention check")

    weak_selected = sum(1 for question in selected if question["id"] in weak_ids)
    weak_new_needed = max(0, weak_target - weak_selected)
    for question in related_pool(weak_items, exclude_seen=True):
        if weak_new_needed <= 0:
            break
        if add(question, "fresh variant from missed concept"):
            weak_new_needed -= 1

    strong_selected = sum(1 for question in selected if question["id"] in strong_ids)
    strong_new_needed = max(0, strong_target - strong_selected)
    for question in related_pool(strong_items, exclude_seen=True):
        if strong_new_needed <= 0:
            break
        if add(question, "fresh retention variant from correct concept"):
            strong_new_needed -= 1

    for question in QUESTION_BANK:
        if len(selected) >= target_count:
            break
        if question["id"] not in seen_attempt_ids:
            add(question, "new mixed PCM coverage")

    for question_id in weak_ids + strong_ids:
        if len(selected) >= target_count:
            break
        question = bank.get(question_id)
        if question:
            add(question, "repeat fallback for spacing mix")

    selected = selected[:target_count]
    repeated_count = sum(1 for question in selected if question["id"] in seen_attempt_ids)
    new_count = len(selected) - repeated_count
    weak_count = sum(1 for question in selected if question["id"] in weak_ids or reasons[question["id"]].startswith("fresh variant"))
    selection_policy = {
        "target_questions": target_count,
        "repeat_ratio_target": repeat_ratio,
        "repeat_questions": repeated_count,
        "new_questions": new_count,
        "actual_repeat_ratio": round(repeated_count / max(len(selected), 1), 2),
        "weak_concept_questions": weak_count,
        "retained_concept_questions": len(selected) - weak_count,
        "history_questions_considered": len(seen_attempt_ids),
        "rule": "80% weak concepts, 20% retained concepts, with 40-60% repeats and the rest fresh concept variants.",
    }
    return _build_test(
        [question["id"] for question in selected],
        attempt_number + 1,
        "Adaptive revision test generated from missed concepts, retained strengths, and fresh PCM variants.",
        reasons,
        selection_policy,
    )


def submit_chemistry_attempt(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InputError("invalid_payload", "Request body must be a JSON object.")

    question_ids = payload.get("question_ids")
    if not isinstance(question_ids, list) or not question_ids:
        raise InputError("missing_questions", "Submit the question ids for the current PCM test.")

    responses = payload.get("responses")
    if not isinstance(responses, dict) or not responses:
        raise InputError("missing_responses", "Answer at least one PCM question before submitting.")

    try:
        attempt_number = max(1, int(payload.get("attempt_number", 1)))
    except (TypeError, ValueError):
        attempt_number = 1

    history = payload.get("history") or []
    if not isinstance(history, list):
        history = []

    bank = _question_by_id()
    unknown = [question_id for question_id in question_ids if question_id not in bank]
    if unknown:
        raise InputError("unknown_question", f"Unknown PCM question id: {unknown[0]}")

    scored = [_score_question(bank[question_id], responses.get(question_id, "")) for question_id in question_ids]
    overall = round(sum(item["score"] for item in scored) / len(scored) * 100)
    weak_focus = [
        f"{item['subject']}: {item['chapter']} -> {item['subtopic']}"
        for item in scored
        if item["score"] < 0.72
    ]
    correct_ids = [item["question_id"] for item in scored if item["correct"]]
    wrong_ids = [item["question_id"] for item in scored if not item["correct"]]

    analysis = {
        "attempt_number": attempt_number,
        "overall_score": overall,
        "verdict": "Strong PCM proof" if overall >= 78 else "Partial PCM proof" if overall >= 50 else "Not enough PCM proof yet",
        "subject_analysis": _bucket_stats(scored, "subject"),
        "domain_analysis": _bucket_stats(scored, "domain"),
        "chapter_analysis": _bucket_stats(scored, "chapter"),
        "subtopic_analysis": _bucket_stats(scored, "subtopic"),
        "question_results": scored,
        "correct_question_ids": correct_ids,
        "wrong_question_ids": wrong_ids,
        "proof_analysis": _proof_analysis(scored),
        "jee_readiness": _jee_readiness(scored),
        "attempt_delta": _attempt_delta(history, overall),
    }
    analysis["review_plan"] = _schedule(attempt_number, overall, weak_focus)
    analysis["next_test"] = _select_revision_questions(scored, attempt_number, history)
    analysis["next_learning_action"] = recommend_for_pcm(analysis)
    return analysis


def submit_pcm_attempt(payload: dict[str, Any]) -> dict[str, Any]:
    return submit_chemistry_attempt(payload)
