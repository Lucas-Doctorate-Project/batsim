{
  description = "Batsim - Lucas Doctorate Project fork";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    kapack = {
      url = "github:oar-team/nur-kapack/master";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, kapack, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-darwin" ];
      forEachSystem = f: nixpkgs.lib.genAttrs systems f;
    in {
      packages = forEachSystem (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          kapackSet = import kapack { inherit pkgs; };
          fixedRedox = kapackSet.redox.overrideAttrs (old: {
            cmakeFlags = (old.cmakeFlags or []) ++ [ "-DCMAKE_POLICY_VERSION_MINIMUM=3.5" ];
          });
          # gtest 1.17 needs C++17 CTAD but intervalset builds with -std=c++14,
          # so its unittest target fails to compile. Drop gtest so the test exe
          # is not built (gtest_dep.found() becomes false) and skip checks.
          fixedIntervalset = kapackSet.intervalset.overrideAttrs (old: {
            buildInputs = [];
            doCheck = false;
          });
          fixedKapack = kapackSet // {
            batsim = kapackSet.batsim.override {
              redox = fixedRedox;
              intervalset = fixedIntervalset;
            };
          };
          jobs = import ./default.nix {
            kapack = fixedKapack;
            doUnitTests = false;
            doCoverage = false;
            # Release build: meson release (-O3, NDEBUG) and a stdenv without
            # keepDebugInfo, instead of the default debug build.
            debug = false;
            useClang = builtins.elem system [ "x86_64-darwin" "aarch64-darwin" ];
          };
        in {
          default = jobs.batsim;
          batsim = jobs.batsim;
        }
      );
    };
}
