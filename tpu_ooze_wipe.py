"""H2D TPU prime-tower wipes only. Python 3.10+, standard library only.
Adds material-specific wipes and relocates explicit tower lifts.
"""
import argparse, hashlib, json, math, os, re, sys, tempfile, zipfile
from pathlib import Path
MODEL = {'Inner wall', 'Outer wall', 'Overhang wall', 'Sparse infill', 'Internal solid infill', 'Top surface', 'Bottom surface', 'Bridge', 'Gap infill', 'Floating vertical shell', 'Ironing'}

SUPPORT = {'Support', 'Support interface', 'Support transition'}

NUM = '[-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)'

PARAM = re.compile('([A-Z])(' + NUM + ')')

OOZE_WIPE_SECONDS = 15
PLA_WIPE_SECONDS = 2
TOWER_EXIT_CLEARANCE_MM = 3
WIPE_MARKER = '; TPU_PRIME_ZIGZAG_V4'

BEGIN = '; TPU_PRIME_ZIGZAG_BEGIN'

END = '; TPU_PRIME_ZIGZAG_END'

def atomic_write(path, data):
    path = Path(path)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def values(cfg, key):
    try:
        result = [float(v) for v in cfg[key].split(',')]
    except (KeyError, ValueError):
        raise ValueError(f'Missing or invalid tower setting: {key}')
    if not all((math.isfinite(v) and v > 0 for v in result)):
        raise ValueError(f'Invalid tower setting: {key}')
    return result

def travel_retraction(cfg, slot):
    settings = []
    for key in ('retraction_length', 'retraction_speed', 'deretraction_speed'):
        base = cfg.get(key, '').strip().split(',')
        overrides = cfg.get('filament_' + key, '').strip().split(',')
        raw = overrides[slot].strip() if slot < len(overrides) else ''
        if raw in ('', 'nil'):
            raw = base[-1].strip() if len(base) in (1, 2) else ''
        try:
            value = float(raw)
        except ValueError:
            raise ValueError(f'Missing or invalid TPU travel setting: {key}')
        if not math.isfinite(value) or value < 0 or (key != 'retraction_length' and value == 0):
            raise ValueError(f'Invalid TPU travel setting: {key}')
        settings.append(value)
    return settings

def travel_parameters(cfg, nozzle, first_layer):

    def setting(key, default=None):
        raw = cfg.get(key)
        if raw is None:
            if default is not None:
                return default
            raise ValueError(f'Missing travel setting: {key}')
        entries = raw.strip().split(',')
        if len(entries) not in (1, 2):
            raise ValueError(f'Unsupported travel setting mapping: {key}')
        value = float(entries[nozzle] if len(entries) == 2 else entries[0])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f'Invalid travel setting: {key}')
        return value
    speed = setting('travel_speed')
    acceleration = setting('travel_acceleration')
    if first_layer:
        acceleration = setting('initial_layer_travel_acceleration', acceleration) or acceleration
    if speed <= 0 or acceleration <= 0:
        raise ValueError('Tower travel requires positive speed and acceleration.')
    return (speed * 60, acceleration)

def tower_eligibility(text, cfg):
    kinds = [v.strip().strip('"') for v in cfg.get('filament_type', '').split(';')]
    mapping = [int(v) for v in cfg.get('filament_map', '').split(',') if v.strip()]
    used = set()
    active = None
    role = ''
    started = False
    prime = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == '; CHANGE_LAYER':
            started = True
        if line.startswith('; FEATURE:'):
            role = line.split(':', 1)[1].strip()
        code = line.split(';', 1)[0].strip()
        if not code:
            continue
        op = code.split()[0]
        match = re.fullmatch('T(\\d+)', op)
        if match:
            active = int(match[1])
            role = ''
        if started and op in {'G1', 'G2', 'G3'}:
            args = dict(PARAM.findall(code[len(op):]))
            if float(args.get('E', '0')) > 0 and any((k in args for k in 'XY')):
                if role == 'Prime tower':
                    prime = True
                if role in MODEL | SUPPORT and active is not None:
                    used.add(active)
    if cfg.get('enable_prime_tower', '').strip() != '1' or not prime:
        return 'No printed prime tower.'
    if not any((i < len(kinds) and kinds[i] == 'TPU' for i in used)):
        return 'No printed TPU filament.'
    if len({mapping[i] for i in used if i < len(mapping)}) < 2:
        return 'Not a dual-nozzle print.'
    return None

def full_prime_bounds(text, core=True):
    """Per-height tower footprint from both nozzles, including later tool runs."""
    result={};sweeps={};vertical_sweeps={};xyz=[None]*3;role='';tower=False;started=False;absolute=True;relative=False;wiping=False
    for raw in text.splitlines():
        line=raw.strip()
        if line=='; CHANGE_LAYER':started=True;role='';tower=False
        if line.startswith('; FEATURE:'):role=line.split(':',1)[1].strip()
        if line=='; WIPE_TOWER_START':tower=True
        if line=='; WIPE_TOWER_END':tower=False
        if line=='; WIPE_START':wiping=True
        if line=='; WIPE_END':wiping=False
        code=line.split(';',1)[0].strip()
        if not code:continue
        op=code.split()[0];p={k:float(v) for k,v in PARAM.findall(code[len(op):])}
        if re.fullmatch(r'T\d+',op):role=''
        if op=='G90':absolute=True
        if op=='G91':absolute=False
        if op=='M83':relative=True
        if op=='M82':relative=False
        if op.startswith(('G28','G150')):xyz=[None]*3
        if op=='G92':xyz=[p.get(k,v) for k,v in zip('XYZ',xyz)]
        if op not in ('G0','G1','G2','G3'):continue
        prev=xyz[:]
        xyz=[p.get(k,v) if absolute else (None if v is None else v+p.get(k,0)) for k,v in zip('XYZ',xyz)]
        if not (started and (tower or role=='Prime tower') and not wiping and p.get('E',0)>0 and any(k in p for k in 'XY')):continue
        if not absolute or not relative or None in prev+xyz or op not in ('G0','G1') or abs(xyz[2]-prev[2])>.001:
            raise ValueError('Cannot establish complete planar prime-tower footprint.')
        if abs(prev[1]-xyz[1])<1e-5 and abs(prev[0]-xyz[0])>5:
            pair=tuple(round(v,2) for v in sorted((prev[0],xyz[0])))
            ys=sweeps.setdefault(round(xyz[2],4),{}).setdefault(pair,[])
            ys.append(xyz[1])
        if abs(prev[0]-xyz[0])<1e-5 and abs(prev[1]-xyz[1])>5:
            pair=tuple(round(v,2) for v in sorted((prev[1],xyz[1])))
            vertical_sweeps.setdefault(round(xyz[2],4),{}).setdefault(pair,[]).append(xyz[0])
        b=result.setdefault(round(xyz[2],4),[float('inf'),float('inf'),-float('inf'),-float('inf')])
        b[:]=[min(b[0],prev[0],xyz[0]),min(b[1],prev[1],xyz[1]),max(b[2],prev[0],xyz[0]),max(b[3],prev[1],xyz[1])]
    if core and re.search(r'^; prime_tower_rib_wall = 1\s*$',text,re.M):
        # Rib extremities are not a filled rectangle. Use the dominant raster core.
        for z in result:
            candidates=[(len(ys),[pair[0],min(ys),pair[1],max(ys)])
                        for pair,ys in sweeps.get(z,{}).items()
                        if len(set(ys))>=3 and max(ys)-min(ys)>2]
            candidates += [(len(xs),[min(xs),pair[0],max(xs),pair[1]])
                           for pair,xs in vertical_sweeps.get(z,{}).items()
                           if len(set(xs))>=3 and max(xs)-min(xs)>2]
            if not candidates:raise ValueError(f'Cannot establish ribbed tower wipe core at Z{z}.')
            result[z]=max(candidates)[1]
    return result


def transform_wipes(text):
    if WIPE_MARKER in text:
        return text, {'already_processed': True}
    if any(f'; TPU_PRIME_ZIGZAG_V{v}' in text for v in (1,2,3)):
        raise ValueError('Re-slice original project to apply the new wipe duration and ribbed-tower paths.')
    if '; TPU_OOZE_TOWER_' in text or '; TPU_OOZE_WIPE_V' in text:
        raise ValueError('Re-slice original project: input already contains the old ooze routine.')
    cfg = dict(re.findall(r'^; (\w+) = (.*)$', text, re.M))
    reason = tower_eligibility(text, cfg)
    if reason:
        return text, {'events': [], 'skipped': reason}
    if cfg.get('printer_model','').strip() != 'Bambu Lab H2D' or cfg.get('print_sequence','').strip() != 'by layer':
        raise ValueError('Prime wipes require H2D by-layer printing.')
    kinds = [s.strip().strip('"') for s in cfg['filament_type'].split(';')]
    mapping = [int(s) for s in cfg['filament_map'].split(',')]
    if cfg.get('physical_extruder_map','').strip() != '1,0' or len(kinds)!=len(mapping):
        raise ValueError('Unsupported H2D nozzle mapping.')
    diameter=values(cfg,'filament_diameter'); flow=values(cfg,'filament_flow_ratio')
    complete_bounds=full_prime_bounds(text)
    lines=text.splitlines(keepends=True); eol='\r\n' if '\r\n' in text else '\n'
    xyz=[None]*3; feed=accel=width=height=None
    active=None; role=''; layer=0; relative=False; absolute=True; wiping=False
    speed=100.; saved_speed=None; bounds={}; candidate=None; inserts={}; reports=[]; skipped=[]
    for i,raw in enumerate(lines):
        line=raw.strip()
        if line=='; CHANGE_LAYER':layer+=1;role=''
        if line.startswith('; FEATURE:'):role=line.split(':',1)[1].strip()
        if line.startswith('; LINE_WIDTH:'):width=float(line.split(':',1)[1])
        if line.startswith('; LAYER_HEIGHT:'):height=float(line.split(':',1)[1])
        if line=='; WIPE_START':wiping=True
        if line=='; WIPE_END':wiping=False
        code=line.split(';',1)[0].strip()
        if not code:continue
        op=code.split()[0]; p={k:float(v) for k,v in PARAM.findall(code[len(op):])}
        if op=='M83':relative=True
        if op=='M82':relative=False
        if op=='G90':absolute=True
        if op=='G91':absolute=False
        if op=='G20':raise ValueError('Inch G-code unsupported.')
        if op=='M204':accel=p.get('S')
        if op=='M220':
            if 'B' in code.split()[1:]:saved_speed=speed
            if 'R' in code.split()[1:]:speed=saved_speed
            if 'S' in p:speed=p['S']
        tool=re.fullmatch(r'T(\d+)',op)
        if tool:
            new=int(tool[1]); new=new if new<len(kinds) else None
            if candidate and active is not None and new is not None and new!=active:
                e=candidate; box=complete_bounds.get(round(e['xyz'][2],4)) if e['bounds'] is not None else None
                if box is None:
                    skipped.append({'layer':e['layer'],'reason':'No prime tower printed at outgoing TPU height.'})
                else:
                    commands,report=make_wipes(e,box,cfg,diameter[active],flow[active],mapping[active]-1)
                    inserts[e['line']]=commands;reports.append(report)
            if new!=active:candidate=None
            active=new;role=''
        if op=='G92':
            if layer and any(k in p for k in 'XYZ'):raise ValueError('Coordinate reset during print unsupported.')
            xyz=[p.get(k,v) for k,v in zip('XYZ',xyz)]
        if op.startswith(('G28','G150')):xyz=[None]*3
        if op not in ('G0','G1','G2','G3'):continue
        prev=xyz[:];feed=p.get('F',feed)
        xyz=[p.get(k,v) if absolute else (None if v is None else v+p.get(k,0)) for k,v in zip('XYZ',xyz)]
        depositing=layer and p.get('E',0)>0 and any(k in p for k in 'XY') and not wiping
        if not depositing:continue
        if role not in MODEL|SUPPORT|{'Prime tower'}:continue
        if not relative or not absolute or None in xyz+prev or None in (feed,accel,width,height,speed):
            raise ValueError('Wipes need known G90/M83 position, feed, acceleration, width and height.')
        if op in ('G2','G3') or abs(xyz[2]-prev[2])>0.001:
            raise ValueError('Disable arc fitting; prime wipes require planar linear deposition.')
        key=round(xyz[2],4)
        if role=='Prime tower':
            b=bounds.setdefault(key,[float('inf'),float('inf'),-float('inf'),-float('inf')])
            b[:]=[min(b[0],prev[0],xyz[0]),min(b[1],prev[1],xyz[1]),max(b[2],prev[0],xyz[0]),max(b[3],prev[1],xyz[1])]
        if active is not None and kinds[active] in ('TPU','PLA'):
            candidate={'line':i,'layer':layer,'xyz':tuple(xyz),'feed':feed,'accel':accel,
                'width':width,'height':height,'speed':speed,'role':role,'slot':active,
                'bounds':list(bounds[key]) if key in bounds else None,'material':kinds[active]}
    out=[WIPE_MARKER+eol]
    for i,line in enumerate(lines):
        out.append(line)
        if i in inserts:out.append(eol.join(inserts[i])+eol)
    return ''.join(out),{'events':reports,'skipped_switches':skipped,'flow_fraction':0.001}


def make_wipes(e,b,cfg,diameter,flow,nozzle):
    full_bounds=list(b)
    inset=max(1.,e['width'])
    x0,y0,x1,y1=b[0]+inset,b[1]+inset,b[2]-inset,b[3]-inset
    if x1<=x0 or y1<=y0:raise ValueError('Printed prime tower is too narrow for inset wipes.')
    xmin,xmax=(0,325) if nozzle==0 else (25,350)
    if not (xmin<=x0<x1<=xmax and 0<=y0<y1<=320):raise ValueError('Prime wipes exceed nozzle reach.')
    points=[(x0+(x1-x0)*n/10,y0 if n%2==0 else y1) for n in range(11)]
    length=sum(math.dist(a,b) for a,b in zip(points,points[1:]))
    material=e.get('material','TPU')
    seconds=PLA_WIPE_SECONDS if material=='PLA' else OOZE_WIPE_SECONDS
    wipe_feed=length/seconds*60
    travel_feed,travel_accel=travel_parameters(cfg,nozzle,e['layer']==1)
    retract,rs,ds=travel_retraction(cfg,e['slot'])
    z=e['xyz'][2];hop=z+max(.4,e['height'])
    if hop>float(cfg['printable_height']):raise ValueError('Wipe clearance exceeds height limit.')
    area=e['height']*(e['width']-e['height']*(1-math.pi/4))
    epmm=area*flow/(math.pi*(diameter/2)**2)*.001
    if epmm<=0:raise ValueError('Invalid wipe extrusion geometry.')
    out=[BEGIN,f'; outgoing {material} slot {e["slot"]}; 10 strokes, {seconds:g} seconds nominal; 0.1% flow',
        'M220 S100',f'G1 E-{retract:g} F{rs*60:g}',f'M204 S{travel_accel:g}',
        f'G1 Z{hop:.5f} F1200',f'G1 X{x0:.5f} Y{y0:.5f} F{travel_feed:g}',
        f'G1 Z{z:.5f} F1200',f'G1 E{retract:g} F{ds*60:g}',
        '; FEATURE: Prime tower',f'; LINE_WIDTH: {e["width"]:g}',f'M204 S{e["accel"]:g}',
        *( [f'M104 T{[1,0][nozzle]} S200 ; begin outgoing TPU cooldown, no wait'] if material=='TPU' else [])]
    for n,(a,b) in enumerate(zip(points,points[1:]),1):
        out.append(f'G1 X{b[0]:.5f} Y{b[1]:.5f} E{math.dist(a,b)*epmm:.8f} F{wipe_feed:.6f} ; wipe {n}')
    out += [f'G1 E-{retract:g} F{rs*60:g}',f'M204 S{travel_accel:g}',f'G1 Z{hop:.5f} F1200',
        f'G1 X{e["xyz"][0]:.5f} Y{e["xyz"][1]:.5f} F{travel_feed:g}',f'G1 Z{z:.5f} F1200',
        f'G1 E{retract:g} F{ds*60:g}',f'M204 S{e["accel"]:g}',f'M220 S{e["speed"]:g}',
        f'G1 F{e["feed"]:g}',f'; FEATURE: {e["role"]}',f'; LINE_WIDTH: {e["width"]:g}',END]
    return out,{'layer':e['layer'],'z_mm':z,'strokes':10,'material':material,'nominal_seconds':seconds,'feed_mm_min':wipe_feed,'bounds_mm':[x0,y0,x1,y1],'whole_tower_bounds_mm':full_bounds,'footprint_source':'both nozzles, full sliced height footprint'}


def clear_tower_lifts(text):
    """Relocate explicit upward moves outside the complete tower envelope.

    Preserve each move's endpoint and modal feed; firmware-internal motion is
    opaque. Include ribs/brim across all heights, not just the wipe raster core.
    """
    marker='; TOWER_LIFTS_CLEAR_V1'
    if marker in text:return text, {'already_processed':True}
    footprints=full_prime_bounds(text, core=False)
    if not footprints:return text, {'changed':0}
    b=[min(v[0] for v in footprints.values()),min(v[1] for v in footprints.values()),
       max(v[2] for v in footprints.values()),max(v[3] for v in footprints.values())]
    margin=TOWER_EXIT_CLEARANCE_MM
    def over(x,y):return b[0]-margin<x<b[2]+margin and b[1]-margin<y<b[3]+margin
    xyz=[None]*3;absolute=True;feed=None;started=False;out=[];events=[]
    eol='\r\n' if '\r\n' in text else '\n'
    for i,raw in enumerate(text.splitlines(keepends=True)):
        line=raw.strip()
        if line=='; CHANGE_LAYER':started=True
        code=line.split(';',1)[0].strip();parts=code.split()
        if not parts:out.append(raw);continue
        op=parts[0];p={k:float(v) for k,v in PARAM.findall(code[len(op):])}
        if op=='G90':absolute=True
        if op=='G91':absolute=False
        if op.startswith(('G28','G150')):xyz=[None]*3
        if op=='G92':xyz=[p.get(k,v) for k,v in zip('XYZ',xyz)]
        if op not in ('G0','G1','G2','G3'):out.append(raw);continue
        prev=xyz[:];feed=p.get('F',feed)
        xyz=[p.get(k,v) if absolute else (None if v is None else v+p.get(k,0)) for k,v in zip('XYZ',xyz)]
        if not started or None in prev+xyz or xyz[2]<=prev[2]+1e-6:
            out.append(raw);continue
        # Test the XY bounding box of the move too: diagonal lifts may cross the tower.
        crosses=not (max(prev[0],xyz[0])<b[0]-margin or min(prev[0],xyz[0])>b[2]+margin or
                     max(prev[1],xyz[1])<b[1]-margin or min(prev[1],xyz[1])>b[3]+margin)
        if not crosses:out.append(raw);continue
        if not absolute or feed is None or abs(p.get('E',0))>1e-9:
            raise ValueError(f'Cannot safely relocate tower lift at line {i+1}: {line}')
        x,y=prev[:2]
        if over(x,y):
            candidates=[(b[0]-margin,y),(b[2]+margin,y),(x,b[1]-margin),(x,b[3]+margin)]
            candidates=[q for q in candidates if 25<=q[0]<=325 and 0<=q[1]<=320]
            if not candidates:raise ValueError('No reachable horizontal tower exit.')
            x,y=min(candidates,key=lambda q:math.dist(q,prev[:2]))
        commands=['; TOWER_CLEAR_LIFT_BEGIN',f'; relocated: {line}',
                  f'G1 X{x:.5f} Y{y:.5f} F6000 ; clear tower horizontally',
                  f'G1 Z{xyz[2]:.5f} F{feed:g} ; lift outside tower',
                  f'G1 X{xyz[0]:.5f} Y{xyz[1]:.5f} F6000',
                  f'G1 F{feed:g}','; TOWER_CLEAR_LIFT_END']
        out.append(eol.join(commands)+eol)
        events.append({'line':i+1,'from':prev,'to':xyz[:],'lift_xy':[x,y]})
    return marker+eol+''.join(out),{'changed':len(events),'envelope':b,'events':events}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--report',type=Path)
    ap.add_argument('--diagnostic-dir',type=Path,help='Save the most recent input/output and report for troubleshooting.')
    args = ap.parse_args()
    try:
        reports = {}
        def process(text):
            result, report = transform_wipes(text)
            if report.get('skipped'):return result, report
            result, report['tower_lifts'] = clear_tower_lifts(result)
            return result, report
        if zipfile.is_zipfile(args.input):
            if args.output is None or args.input.resolve() == args.output.resolve():
                raise ValueError('3MF input requires a DIFFERENT --output file.')
            import io
            buf = io.BytesIO()
            with zipfile.ZipFile(args.input) as zin:
                edits = {}
                for name in zin.namelist():
                    if name.endswith('.gcode'):
                        result, reports[name] = process(zin.read(name).decode('utf-8'))
                        edits[name] = result.encode('utf-8')
                        checksum = name+'.md5'
                        if checksum in zin.namelist():
                            edits[checksum] = hashlib.md5(edits[name]).hexdigest().encode('ascii')
                if not reports: raise ValueError('Archive contains no G-code.')
                with zipfile.ZipFile(buf,'w') as zout:
                    for info in zin.infolist(): zout.writestr(info,edits.get(info.filename,zin.read(info.filename)))
            atomic_write(args.output,buf.getvalue())
        else:
            text = args.input.read_bytes().decode('utf-8')
            if args.diagnostic_dir:
                args.diagnostic_dir.mkdir(parents=True,exist_ok=True)
                atomic_write(args.diagnostic_dir/'input.gcode',text.encode('utf-8'))
            result, reports['gcode'] = process(text)
            if args.diagnostic_dir:
                atomic_write(args.diagnostic_dir/'output.gcode',result.encode('utf-8'))
            atomic_write(args.output or args.input,result.encode('utf-8'))
        payload = json.dumps(reports,indent=2)
        if args.report: atomic_write(args.report,payload.encode('utf-8'))
        if args.diagnostic_dir:
            atomic_write(args.diagnostic_dir/'report.json',payload.encode('utf-8'))
        print(payload)
    except (ValueError,OSError,UnicodeError,zipfile.BadZipFile) as exc:
        print('TPU prime-tower wipe: '+str(exc),file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
