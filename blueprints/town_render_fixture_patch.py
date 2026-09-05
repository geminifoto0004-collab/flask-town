"""Connect persisted native-fixture counts to the base canvas renderer."""


def patch_render_fixtures(html: str) -> str:
    signature = "  function drawDesk(a){"
    if signature not in html:
        raise ValueError("Town desk renderer anchor changed")

    start = html.index(signature)
    end = html.index("\n  function ", start + len(signature))
    desk = html[start:end]
    desk = desk.replace(signature, "  function drawDesk(a,deskIndex=0){", 1)
    desk = desk.replace(
        "    const x=a.homeX;",
        "    const x=a.homeX;\n    const showComputer=deskIndex<Number(townFixtureCounts.computer||0);",
        1,
    )

    monitor_start = desk.find("    // 螢幕本體")
    keyboard_start = desk.find("    // 鍵盤、滑鼠")
    if monitor_start < 0 or keyboard_start < 0:
        raise ValueError("Town computer renderer anchors changed")
    monitor_block = desk[monitor_start:keyboard_start]
    monitor_lines = monitor_block.splitlines()
    wrapped_monitor = monitor_lines[0] + "\n    if(showComputer){\n" + "\n".join("  " + line for line in monitor_lines[1:]) + "\n    }\n\n"
    desk = desk[:monitor_start] + wrapped_monitor + desk[keyboard_start:]

    peripherals = (
        "    rect(x-19,191,38,5,'#b8ab93');\n"
        "    for(let k=0;k<6;k++)px(x-16+k*5,192,3,2,'#817769');\n"
        "    px(x+24,191,5,4,'#3d4650');"
    )
    if peripherals not in desk:
        raise ValueError("Town computer peripheral anchors changed")
    desk = desk.replace(peripherals, "    if(showComputer){\n" + "\n".join("  " + line for line in peripherals.splitlines()) + "\n    }", 1)

    helper = """  const townFixtureCounts={computer:3};
  function applyTownFixtureCounts(world){
    const raw=world&&world.fixtureCounts&&typeof world.fixtureCounts==='object'?world.fixtureCounts:{};
    if(Number.isFinite(Number(raw.computer)))townFixtureCounts.computer=Math.max(0,Math.min(3,Math.trunc(Number(raw.computer))));
  }

"""
    html = html[:start] + helper + desk + html[end:]
    html = html.replace(
        "    agents.forEach(a=>depthItems.push({y:228,draw:()=>drawDesk(a)}));",
        "    agents.forEach((a,index)=>depthItems.push({y:228,draw:()=>drawDesk(a,index)}));",
        1,
    )
    html = html.replace(
        "    if(!world||typeof world!=='object')return false;",
        "    if(!world||typeof world!=='object')return false;\n    applyTownFixtureCounts(world);",
        1,
    )

    marker = "  registerDirectorTool('agent_action',action=>{"
    if marker not in html:
        raise ValueError("Town director tool anchor changed")
    handler = """  registerDirectorTool('set_fixture_count',action=>{
    const fixture=String(action.fixture||'');
    if(fixture!=='computer')return;
    townFixtureCounts.computer=Math.max(0,Math.min(3,Math.trunc(Number(action.count)||0)));
    addLog('办公室电脑数量已设为 '+townFixtureCounts.computer+' 台');
  });
"""
    return html.replace(marker, handler + marker, 1)

