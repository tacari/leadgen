{pkgs}: {
  deps = [
    pkgs.graalvmCEPackages.graalnodejs
    pkgs.postgresql
    pkgs.glibcLocales
  ];
}
