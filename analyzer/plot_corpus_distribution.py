import numpy as np
import matplotlib.pyplot as plt
import argparse
import os

plt.rcParams['pdf.fonttype'] = 42
# plt.rcParams['ps.fonttype'] = 42 # for .eps

def plot(corpus_lens_set, legends, out_dir):
    x = np.arange(len(corpus_lens_set[0]))  # the x locations for the groups
    width = 0.13  # the width of the bars

    fig, ax = plt.subplots(figsize=(30, 10))
    # Define hatch patterns
    colors = ['#F5F5F5', 'white', '#505050', '#DCDCDC', '#E5E5E5', 'white', 'white']
    hatchs = ['', '//', '', '..', 'OO', 'xx', 'oo']

    # Create bars using different hatch patterns for black and white style
    for i, corpus_lens in enumerate(corpus_lens_set):
        ax.bar(x + i * width, corpus_lens, width, label=legends[i], color=colors[i], edgecolor='black', hatch=hatchs[i])

    # Labels, titles and custom x-axis tick labels, etc.
    ax.set_xlabel('Program Length (Number of Syscall Invocations)', fontsize=30)
    ax.set_ylabel('Proportion (%)', fontsize=30)
    ax.tick_params(axis='both', which='major', labelsize=28)
    ax.set_xticks(x + width * (len(corpus_lens_set) - 1) / 2)
    ax.set_xticklabels(['1', '2', '3', '4', '5+'])

    # Add text labels above the bars
    for i, corpus_lens in enumerate(corpus_lens_set):
        for j, val in enumerate(corpus_lens):
            ax.text(x[j] + width * i, val + 1, f'{val:.2f}', ha='center', fontsize=15)

    ax.legend(fontsize=26)

    # Save the figure
    fig.savefig(os.path.join(out_dir, 'distribution_prog_length.png'), bbox_inches='tight')
    fig.savefig(os.path.join(out_dir, 'distribution_prog_length.pdf'), dpi=600, format='pdf', bbox_inches='tight')
    print('[+] plot done!')


def main():
    parser = argparse.ArgumentParser(description='Plot the distribution of corpus')
    parser.add_argument('-o', '--out_dir', type=str, help='out dir to save the plot fig')
    args = parser.parse_args()

    # Sample data
    corpus_lens_1 = [25.59, 22.72, 14.36, 10.18, 27.15]
    corpus_lens_2 = [0.32, 3.22, 6.11, 12.54, 77.81]
    corpus_lens_3 = [0.31, 0.00, 0.31, 0.94, 98.43]
    corpus_lens_4 = [4.00, 9.67, 13.00, 17.67, 55.67]
    corpus_lens_5 = [22.89, 16.87, 9.94, 12.65, 37.65]
    corpus_lens_6 = [88.24, 5.88, 1.47, 1.47, 2.94]
    corpus_lens_7 = [43.59, 9.40, 17.09, 10.26, 19.66]

    corpus_lens_set = [corpus_lens_1, corpus_lens_2, corpus_lens_3, corpus_lens_4, corpus_lens_5, corpus_lens_6, corpus_lens_7]
    legends = ["SyzGPT-GPT-3.5", "SyzGPT-GPT-4", "SyzGPT-Claude-3.5-Sonnet", "SyzGPT-Llama-3", "SyzGPT-CodeLlama", "Zero-shot-GPT-3.5", "Few-shot-GPT-3.5"]

    out_dir = args.out_dir or '.'
    plot(corpus_lens_set, legends, out_dir)

    print('[+] plot_corpus_distribution done!')


if __name__ == '__main__':
    main()