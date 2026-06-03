export function calcBaseScore(cpuCores, ramGb, storageGb) {
  return cpuCores * 10 + ramGb * 5 + storageGb * 0.1;
}
