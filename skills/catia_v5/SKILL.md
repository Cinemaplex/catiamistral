# Référence automatisation CATIA V5-6R2017 (VBScript)

Modèle objet COM de CATIA V5 accessible en VBScript. Toute macro exécutée par le
worker part de ces conventions.

## Démarrage type

```vbscript
Option Explicit
Dim CATIA, doc, part
On Error Resume Next
Set CATIA = GetObject(, "CATIA.Application")
If Err.Number <> 0 Then Err.Clear : Set CATIA = CreateObject("CATIA.Application")
CATIA.Visible = True
On Error Goto 0

Set doc = CATIA.Documents.Add("Part")       ' nouveau PartDocument
Set part = doc.Part
part.Update()
' Le worker sauvegarde ensuite : doc.SaveAs "C:\...\output\nom.CATPart"
```

Ne jamais appeler CATIA is not running via `GetObject` seul : gérer l'erreur et
retomber sur `CreateObject`.

## Structure d'une Part

- `part.Bodies` : corps solides. `Set body1 = part.Bodies.Add()`.
- `part.HybridBodies` : sets géométriques (wireframe/surfaces).
  `Set hb = part.HybridBodies.Add()` puis `hb.AppendHybridShape shape`.
- `part.OriginElements.PlaneXY / PlaneYZ / PlaneXZ` : plans de référence.
- `part.MainBody` : corps principal.
- `part.Update()` à la fin de chaque bloc de création IMPORTANT.

## Esquisses (Sketcher)

```vbscript
Dim skh As Sketch
Set skh = body1.Sketches.Add(part.OriginElements.PlaneXY)
Dim factory2D As Factory2D
Set factory2D = skh.OpenEdition()

Dim l1 As Line2D
Set l1 = factory2D.CreateLine(x1, y1, x2, y2)      ' coordonnées en mm, plan XY
Dim c1 As Circle2D
Set c1 = factory2D.CreateClosedCircle(xc, yc, rayon)
Dim r1 As Rectangle2D
Set r1 = factory2D.CreateRectangle(x1, y1, x2, y2)

skh.CloseEdition()
```

Contraintes optionnelles (les cotes exactes viennent des coordonnées) :
`skh.Constraints.AddBiEltCstDeg` etc. Ne pas sur-contraindre : le modèle de
géométrie reste calculé à partir des coordonnées 2D.

## Licences de la station (MD2 / GSD / ST1)

Le worker déclare les licences attendues via `CATIAMISTRAL_LICENSES` (défaut
`MD2,GSD,ST1`). A quoi elles servent en automation :

- **MD2** (Mechanical Design 2) : esquisses, Pad/Pocket/Shaft, Assembly,
  paramètres. Toute macro de pièces solides s'appuie dessus.
- **GSD** (Generative Shape Design) : HybridShapeFactory étendu — surfaces
  complexes, offset/fill/join avancés, lois. Les appels GSD échouent si la
  capa manque.
- **ST1** (STEP Core Interface) : `Documents.NewFrom("fichier.step")` pour
  importer un STEP ; IGES exige IG1 (souvent présent). Le worker l'utilise
  pour les jobs de relevé dimensionnel (type `measure`).

Une erreur type "No more licenses available" / "license is not granted" se
traduit côté worker par le statut `license_error` (message + liste attendue).
En macro, ne pas deviner une capa absente : tester/enchaîner plutôt GSD
uniquement quand le plan le requiert.

## Contraintes d'esquisse (étude complète avec contraintes)

Créer des contraintes robustes (autour d'une géométrie déjà posée) :

```vbscript
Dim cst As Constraint
' Axe d'enum CatConstraintType : valeurs numeriques (VBScript n'a pas les
' constantes nommees VBA). Exemples usuels : 1 = On (coincidence simple),
' 2 = Distance, 3 = Length, 4 = Radius, 6 = Horizontality, 7 = Verticality.
Set cst = skh.Constraints.AddBiEltCst(2, l1, originPlaneOrLine)   ' distance
Set cst = skh.Constraints.AddTriEltCst(<angle>, l1, l2, sommet)   ' angle
' Optionnel : rendre la cote pilotante puis la changer
' cst.Mode = 0                       ' catCstModeDrivingDimension
' cst.Value.Value = 47.5             ' nouveau rayon/distance (unités SI base?)
part.Update()
```

Règle de robustesse : commencer avec 2-3 contraintes (distance/rayon),
`part.Update()`, vérifier le résultat (statut + mesures du worker), puis
ajouter. En cas d'erreur de contrainte (message CATIA), corriger la macro et
reposer un job - ne jamais empiler 10 contraintes en un bloc de première fois.
En VBScript les constantes d'enum n'existent pas : passer les valeurs
numériques et valider par le test.

## Volume : Pad / Pocket / Shaft

```vbscript
Dim pad As Pad
Set pad = body1.AddNewPad(skh, epaisseur_mm)      ' extrusion de l'esquisse
Dim pocket As Pocket
Set pocket = body1.AddNewPocket(skh2, profondeur_mm)  ' alésage/enlèvement
Dim shaft As Shaft
Set shaft = body1.AddNewShaft(skh3)               ' révolution (axe inclus esquisse)
pad.SecondDirectionAngle.Value = angle            ' optionnel
```

Symétrie miroir : `body1.AddNewMirror(planOuFace)`.

## Wireframe et surfaces (HybridShapeFactory)

```vbscript
Dim hsf As HybridShapeFactory : Set hsf = part.HybridShapeFactory
Dim p1 As HybridShapePointCoord
Set p1 = hsf.AddNewPointCoord(0.0, 0.0, 10.0)
hb.AppendHybridShape p1 : part.Update()             ' Update après chaque shape référencée

Dim ln As HybridShapeLinePtPt
Set ln = hsf.AddNewLinePtPt(p1, p2)
Dim ci As HybridShapeCircleCtrRad
Set ci = hsf.AddNewCircleCtrRad(p1, planOuFace, rayon, 1)  ' sens = 1 ou -1
Dim sp As HybridShapeSpline
Set sp = hsf.AddNewSpline()  ' puis sp.AddPointWithConstraintExplicit(pt) par point
Dim ex As HybridShapeExtrude
Set ex = hsf.AddNewExtrude(sketchOrCurve, longueur, 0.0)
Dim of As HybridShapeOffset
Set of = hsf.AddNewOffset(surface, distance, 1, 0)
Dim jn As HybridShapeAssemble
Set jn = hsf.AddNewAssemble()
Dim fll As HybridShapeFill
Set fll = hsf.AddNewFill()
```

Opérations booléennes entre corps :
`body1.AddNewSolidCombine(-1, body2)` (union/+), `(0, body2)` soustraction,
`(-2, body2)` intersection. Paramètres en constantes : -1 = union, 0 = diff,
-2 = inter.

## Paramètres pilotants (recommandé)

Créer des paramètres puis piloter les dimensions par formule = plus robuste pour
une pièce paramétrique :

```vbscript
Dim params As Parameters : Set params = part.Parameters
Dim largeur As Dimension
Set largeur = params.CreateDimension("", "LENGTH", 100.0)
largeur.Rename "Largeur"
' Liaison : pad.FirstLimit.Dimension.Value = largeur.Value  (ou formule)
```

## Pièces à éviter (V5-6R2017, COM)

- Pas de `MsgBox` bloquant ni `InputBox` : exécution sans interaction.
- Ne pas utiliser les workbenches interactifs (CATStFreeStyle etc.) : se limiter
  à Part Design + GSD de base.
- Ne pas référencer des sélections interactives (`.SelectElement2`) : worker
  sans écran d'interaction.
- Encodage latin-1 : pas d'accents dans la macro (chaînes incluses).
- Chemins Windows : `C:\...` avec `\`. Le worker sauvegarde sous `output/`.

## Mesures après exécution

Le worker renvoie automatiquement dans le résultat :
- `part_name`, nombre de `Bodies`,
- masse en kg via SPAWorkbench (si licence disponible),
- capture d'écran de la vue active (.jpg).

Pour fournir plus de mesures, la macro peut les écrire dans une variable et le
worker les remonte : garder la macro simple, l'agent analysera result.json.

Le worker sait aussi faire un relevé dimensionnel complet d'un fichier existant
(`type: "measure"`, déposé via create_measure_job) : ouverture du .CATPart /
.CATProduct / .CATShape / .CGR (ou import .step/.stp via Documents.NewFrom si
ST1), puis SPAWorkbench sur le corps principal :

- masse (`GetMass`) en kg, volume (`GetVolume`) en m3, surface (`GetArea`) en m2 ;
- centre de gravité (`GetCOG`) en mètres ;
- nombre de corps et d'esquisses ;
- paramètres pilotants (nom + valeur, max 200).

Résultat publié dans result.json, champ `dimensions` (un objet par fichier,
avec erreurs éventuelles par fichier). Unités SI.

Dans une macro de conception, la même API est utilisable pour vérifier les
mesures cibles :

```vbscript
Dim spa As Workbench : Set spa = doc.GetWorkbench("SPAWorkbench")
Dim meas : Set meas = spa.GetMeasurable(refBody)
Dim masse: masse = meas.GetMass()   ' kg - à comparer à l'exigence client
```
