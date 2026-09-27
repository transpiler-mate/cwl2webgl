cwlVersion: v1.2
$namespaces:
  s: https://schema.org/
s:name: Hello workflow
s:description: Capture an echo greeting in a file
s:dateCreated: "2026-09-22"
s:license: https://spdx.org/licenses/Apache-2.0
s:softwareVersion: 1.0.0
s:softwareHelp:
  s:name: Hello workflow documentation
  s:url: https://Transpiler-Mate.github.io/cwl2webgl/tutorials/first-steps/
s:publisher:
  s:name: Transpiler-Mate
s:author:
  s:givenName: Ada
  s:familyName: Lovelace
  s:email: ada@example.org
  s:affiliation:
    s:name: Example organization
$graph:
  - id: main
    class: Workflow
    label: Hello workflow
    inputs:
      message:
        type: string
        default: Hello, world!
    outputs:
      greeting:
        type: File
        outputSource: echo/greeting
    steps:
      echo:
        in:
          message: message
        out: [greeting]
        run: "#echo-tool"
  - id: echo-tool
    class: CommandLineTool
    baseCommand: echo
    inputs:
      message:
        type: string
        inputBinding:
          position: 1
    stdout: greeting.txt
    outputs:
      greeting:
        type: File
        outputBinding:
          glob: greeting.txt
