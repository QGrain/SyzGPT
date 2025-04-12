import os
import matplotlib.pyplot as plt


def calc_avg(d):
    return int(sum(d)/len(d))


common_syscalls = [349, 347, 339, 331, 323]
uncovered_syscalls = [17, 14, 14, 14, 13]
unstable_syscalls = [0, 5, 13, 21, 30]

raw_variants = [2568, 2485, 2613, 2397, 2611]
avg_variants = [calc_avg(raw_variants[:i]) for i in range(1, len(raw_variants)+1)]
common_variants = [2568, 2195, 1760, 1496, 1326]
uncovered_variants = [1878, 1219, 1066, 948, 881]
unstable_variants = [0, 1032, 1620, 2002, 2239]
total_variants = [4446, 4446, 4446, 4446, 4446]
disabled_variants = [548, 548, 548, 548 ,548]

x = list(range(1, len(common_variants) + 1))

plt.figure(figsize=(10, 7))

# plt.plot(x, total_variants, marker='o', label='Total', linestyle='-', linewidth=2, markersize=7, color='green')
# plt.plot(x, disabled_variants, marker='o', label='Disabled', linestyle='-', linewidth=2, markersize=7, color='red')
plt.plot(x, uncovered_variants, marker='s', label='Common uncovered', linestyle='--', linewidth=2, markersize=7, color='red')
plt.plot(x, avg_variants, marker='^', label='Average covered', linestyle='-.', linewidth=2, markersize=7, color='blue')
plt.plot(x, common_variants, marker='o', label='Common covered', linestyle='-', linewidth=2, markersize=7, color='green')

for i, (x_val, y_val) in enumerate(zip(x, uncovered_variants)):
    plt.text(x_val, y_val + 18, str(y_val), ha='center', va='bottom', fontsize=14)

for i, (x_val, y_val) in enumerate(zip(x, avg_variants)):
    plt.text(x_val, y_val + 18, str(y_val), ha='center', va='bottom', fontsize=14)

for i, (x_val, y_val) in enumerate(zip(x, common_variants)):
    plt.text(x_val, y_val + 18, str(y_val), ha='center', va='bottom', fontsize=14)

# plt.title('24h fuzzing with Syzkaller', fontsize=24)
plt.xlabel('Repeat times', fontsize=20)
plt.ylabel('Number of syscalls', fontsize=20)
plt.yticks(fontsize=18)
plt.xticks(x, fontsize=18)
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend(fontsize=20)

plt.tight_layout()

plt.savefig('new_variants_coverage_plot.png', dpi=300)
plt.savefig('new_variants_coverage_plot.eps', format='eps')

plt.show()
