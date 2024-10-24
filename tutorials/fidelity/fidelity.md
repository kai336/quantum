# 密度行列とは
## 量子状態
量子状態 $`\ket{\psi}`$ は大きさが1の列ベクトル

$$\ket{\psi} = \begin{pmatrix}\alpha_1 \\ \vdots \\ \alpha_n\end{pmatrix} \in \mathbb{C}^n$$
で定義される。

## 密度行列
密度行列 $`\rho`$ はある量子状態のもつ列ベクトル同士の外積

$$\rho = \ket{\psi}\bra{\psi} =\begin{pmatrix}\alpha_1 \\ \vdots \\ \alpha_n\end{pmatrix} \begin{pmatrix}\alpha_1^* & \dots & \alpha_n^*\end{pmatrix} \in \mathbb{C}^{n^2} $$
で定義される。

### １量子ビット系の例
例として１量子ビット系について考える。最も単純な量子状態として、$`\ket{0} = \begin{pmatrix}1 \\ 0 \end{pmatrix}, \ket{1} = \begin{pmatrix}0 \\ 1 \end{pmatrix}`$ の2つのベクトルを基底状態とすることができる。このベクトルの第一、第二成分はそれぞれ状態 $`\ket{0}, \ket{1}`$ が観測される確率(各成分は複素数のため、絶対値の2乗が確率になる)を表している。

ここで、任意の１量子ビットの量子状態 $`\ket{\psi} = \begin{pmatrix}\alpha \\ \beta\end{pmatrix}`$ の密度行列を以下に計算する。 

$$\rho = \ket{\psi}\bra{\psi} =\begin{pmatrix}\alpha \\ \beta\end{pmatrix} \begin{pmatrix}\alpha^* & \beta^*\end{pmatrix} = \begin{pmatrix}
  |\alpha|^2 & \alpha \beta^* \\
  \beta \alpha^* & |\beta|^2
\end{pmatrix}$$

対角成分がそれぞれの状態が観測される確率を表している。

また、重ね合わせ状態である $`\ket{\psi} = \frac{1}{\sqrt{2}}\ket{0}+\frac{1}{\sqrt{2}}\ket{1}=\begin{pmatrix}\frac{1}{\sqrt{2}} \\ \frac{1}{\sqrt{2}}\end{pmatrix}`$ の密度行列を以下に計算する。

$$
\rho = \begin{pmatrix}
  1/2 & 1/2 \\
  1/2 & 1/2
\end{pmatrix}
$$

非対角成分は量子状態の重ね合わせや干渉(コヒーレンス)を表している。

# 純粋状態・混合状態とは
## 純粋状態
列ベクトルで表現できる状態
### 例：$`\ket{0}, \ket{1}`$ の重ね合わせ状態
$`\ket{\psi} = \frac{1}{\sqrt{2}}\ket{0}+\frac{1}{\sqrt{2}}\ket{1}=\begin{pmatrix}\frac{1}{\sqrt{2}} \\ \frac{1}{\sqrt{2}}\end{pmatrix}`$

## 混合状態
複数の純粋状態が確率的に混合している状態であり、純粋状態のもつ密度行列の組み合わせで表現できる
### 例：$\ket{0}, \ket{1}$ である確率がそれぞれ $p, 1-p$ であるとき
$$\begin{align}
  \rho &= p\ket{0}\bra{0} + (1-p)\ket{1}\bra{1}\nonumber \\
&= p\begin{pmatrix}1&0\\0&0\end{pmatrix} + (1-p)\begin{pmatrix}0&0\\0&1\end{pmatrix}\nonumber \\&= \begin{pmatrix}p&0\\0&1-p\end{pmatrix} \nonumber
\end{align}$$

# fidelity(忠実度) とは
純粋状態 $`\ket{\psi}`$ と混合状態 $`\rho`$

$$F(\ket{\psi}, \rho) = \bra{\psi}\rho\ket{\psi}$$

混合状態同士

$$F(\rho, \sigma) = \left( Tr\sqrt{\sqrt{\rho}\sigma\sqrt{\rho}}) \right)^2$$

- 2つの状態がどれだけ近い状態にあるかを計算する
- ノイズの影響を受けてデコヒーレンスした量子状態(混合状態)がどれだけ理想の量子状態に近い状態を保っているか、という指標として用いられる
## Werner States
Bell状態にノイズを加えたモデル

$$\rho_W=p\ket{\Phi_+}\bra{\Phi_+}+(1−p)I/4
​$$

- $`p=1`$ のとき、Bell状態と一致
- $`p`$ が増加するほど完全に混合した状態 $`I/4`$ の項が増えてランダムな状態になる
## Bell状態とのfidelity
$$ \begin{align}
F &= \bra{\Phi_+}\rho_W\ket{\Phi_+} \nonumber \\
&= \bra{\Phi_+}\left( p\ket{\Phi_+}\bra{\Phi_+}+(1−p)\frac{I}{4} \right)\ket{\Phi_+} \nonumber \\
&= p\bra{\Phi_+}\ket{\Phi_+}\bra{\Phi_+}\ket{\Phi_+} + (1-p) \bra{\Phi_+}\frac{I}{4}\ket{\Phi_+} \nonumber \\
&= p + (1-p)\times\frac{1}{4}\bra{\Phi_+}\ket{\Phi_+} \nonumber \\
&= p + \frac{1-p}{4} = \frac{3p+1}{4} \nonumber
\end{align} $$

