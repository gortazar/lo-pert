{
  description = "lo-pert — PERT (activity-on-arrow) diagrams for LibreOffice Draw and Impress";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        version = builtins.replaceStrings [ "\n" ] [ "" ] (builtins.readFile ./VERSION);

        # PyUNO in nixpkgs is linked against this very python3, so the test
        # interpreter and the one inside LibreOffice are the same build: `import uno`
        # then works from the dev shell with nothing more than PYTHONPATH pointing at
        # program/ (scripts/with-soffice.sh does that).
        # pytest-cov is used only by the coverage job in ci.yml: `nix flake check` does not
        # measure coverage, because a report is an artefact that has to leave the sandbox
        # and a check keeps nothing but its own success.
        python = pkgs.python3.withPackages (ps: [ ps.pytest ps.hypothesis ps.pytest-cov ]);

        # `nix build` — the installable extension.
        oxt = pkgs.runCommand "lo-pert-${version}.oxt"
          {
            src = ./.;
            nativeBuildInputs = [ pkgs.bash pkgs.zip pkgs.unzip pkgs.python3 ];
          } ''
          cp -r "$src" ./source
          chmod -R u+w ./source
          cd ./source
          # `bash ./build.sh`, not `./build.sh`: the build sandbox has no
          # /usr/bin/env for the shebang to resolve.
          bash ./build.sh "$PWD/dist"
          mkdir -p "$out"
          cp dist/lo-pert-${version}.oxt "$out/"
        '';
      in {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.libreoffice # soffice, unopkg, and the pyuno the tests import
            pkgs.zip
            pkgs.unzip
            pkgs.git
            pkgs.jq
            pkgs.libxml2 # xmllint, for the .xcu and description.xml
          ];

          shellHook = ''
            echo "lo-pert dev shell (version ${version})"
            echo "  pytest tests/unit          pure core, no LibreOffice needed"
            echo "  ./build.sh                 dist/lo-pert-${version}.oxt"
            echo "  pytest tests/integration   headless soffice, installs the .oxt"
            export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
          '';
        };

        checks = {
          # The core is UNO-free by construction, so its tests are a plain python
          # derivation — no LibreOffice in this closure at all.
          unit = pkgs.runCommand "lo-pert-unit-tests"
            {
              src = ./.;
              nativeBuildInputs = [ python ];
            } ''
            cp -r "$src" ./source
            chmod -R u+w ./source
            cd ./source
            PYTHONPATH="$PWD/src" pytest tests/unit -q | tee "$out"
          '';

          # The tests that install the built .oxt into a throwaway profile and drive
          # the menu commands over the UNO bridge. They run inside the build sandbox:
          # LibreOffice needs a writable HOME, and the bridge only ever talks to
          # 127.0.0.1, which the sandbox's own loopback provides.
          headless = pkgs.runCommand "lo-pert-headless-tests"
            {
              src = ./.;
              # zip because the tests build the .oxt they install, and coreutils
              # for build.sh; the sandbox has nothing on PATH that is not here.
              nativeBuildInputs = [ python pkgs.libreoffice pkgs.bash pkgs.zip ];
            } ''
            cp -r "$src" ./source
            chmod -R u+w ./source
            cd ./source
            export HOME="$TMPDIR/home"
            mkdir -p "$HOME"
            pytest tests/integration -q | tee "$out"
          '';

          # A build that produces an .oxt missing a manifest entry installs fine and
          # contributes no menu, so check the archive's contents here rather than
          # discovering it by hand after a release.
          package = pkgs.runCommand "lo-pert-package"
            {
              nativeBuildInputs = [ pkgs.unzip ];
            } ''
            oxt="${oxt}/lo-pert-${version}.oxt"
            unzip -l "$oxt"
            for entry in description.xml META-INF/manifest.xml Addons.xcu \
                ProtocolHandler.xcu lopert_handler.py pythonpath/lopert/network.py; do
              unzip -l "$oxt" | grep -q " $entry$" \
                || { echo "the .oxt is missing $entry" >&2; exit 1; }
            done
            echo "package OK" > "$out"
          '';
        };

        packages.default = oxt;
        packages.oxt = oxt;
      });
}
