import pathlib, subprocess, sys

known_sizes = {
'boundedbyte': '410,83',
'tlranda': '266,71',
}

for arg in sys.argv[1:]:
    # Measure only when necessary
    if arg in known_sizes:
        print(known_sizes[arg])
        continue

    # Use config to ensure proper up-to-date variables
    with open('overlay_username.sh','r') as f:
        config = {}
        for line in f.readlines():
            for key in ['FONT','FONTSIZE','BORDER']:
                if line.startswith(f'{key}='):
                    # Extracting value from line formatted as:
                    # KEY="VALUE";
                    config[key] = line.rstrip().split('=',1)[1].strip(';').strip('"')
    # Use /tmp to usually not clobber anything important -- unlink it later
    tmp_file = pathlib.Path("/tmp/output.png")
    numeral = 0
    # Guaranteed non-clobbersome
    while tmp_file.exists():
        tmp_file = pathlib.Path(f"/tmp/output_{numeral}.png")
        numeral += 1
    # It's split up this way so that a string with spaces doesn't get ruined
    draw_cmd_1 = f"convert -background none -fill white "+\
                 f"-font {config['FONT']} -pointsize {config['FONTSIZE']} "
    draw_cmd_fill = f"label:{arg}"
    draw_cmd_2 = f"-trim +repage -bordercolor none -border {config['BORDER']} "+\
                 f"{tmp_file}"
    subprocess.run(draw_cmd_1.split()+[draw_cmd_fill]+draw_cmd_2.split())
    measure_result = subprocess.run(f"identify {tmp_file}".split(),
                                    stdout=subprocess.PIPE
                                    ).stdout
    tmp_file.unlink()
    # NAME FORMAT SIZE ...
    measurement = measure_result.decode('utf-8').split()[2].replace('x',',')

    known_sizes[arg] = measurement
    with open('track_sizes.py', 'r') as i:
        original_script = i.readlines()
    with open('track_sizes.py','w') as o:
        for line in original_script[0:5]: # Header
            o.write(line)
        o.write(f"'{arg}': '{known_sizes[arg]}',"+"\n") # Content Update
        print(known_sizes[arg])
        for line in original_script[5:]: # Footer
            o.write(line)

